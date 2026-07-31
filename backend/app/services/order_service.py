import math

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.stock_movement import MovementType
from app.schemas.order import OrderCreate, OrderListResponse, OrderResponse
from app.schemas.stock_movement import StockAdjustRequest
from app.services.product_service import PRODUCTS_CACHE_PATTERN
from app.services.stock_service import (
    ALL_MOVEMENTS_CACHE_PATTERN,
    STOCK_HISTORY_CACHE_PATTERN,
    StockService,
)
from app.utils.redis_client import cache_delete_pattern

logger = structlog.get_logger()


class OrderService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    async def create_order(
        self,
        data: OrderCreate,
        created_by: str,
        created_by_name: str,
    ) -> Order:
        """
        Creates an order with all its items.
        For each item: validates stock, creates OrderItem, triggers SHIP movement.
        Everything commits atomically — all succeeds or nothing is saved.
        """

        # 1. Validate all products BEFORE touching any data
        #    We do a full pre-flight check first so we never create a partial order
        validated_items = []
        for item in data.items:
            result = await self.db.execute(
                select(Product).where(
                    Product.id == item.product_id,
                    Product.is_active,
                )
            )
            product = result.scalar_one_or_none()

            if product is None:
                raise ValueError(
                    f"Product {item.product_id!r} not found or is inactive"
                )

            if product.quantity < item.quantity:
                raise ValueError(
                    f"Insufficient stock for {product.sku!r}. "
                    f"Requested: {item.quantity}, available: {product.quantity}"
                )

            validated_items.append((item, product))

        # 2. Create the Order record
        order = Order(
            customer_name=data.customer_name,
            created_by=created_by,
            status=OrderStatus.PENDING,
        )
        self.db.add(order)
        await self.db.flush()  # get order.id before creating items

        # 3. Create OrderItems + trigger SHIP movements
        #    StockService owns all stock logic — we call it, never duplicate it
        stock_service = StockService(self.db)

        for item, product in validated_items:
            # 3a. Create the OrderItem with full snapshot
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,       # snapshot
                product_sku=product.sku,          # snapshot
                quantity=item.quantity,
                unit_price=product.price,         # snapshot
            )
            self.db.add(order_item)

            # 3b. Trigger SHIP movement via StockService
            #     quantitychange is negative for SHIP — we negate here
            await stock_service.adjust_stock(
                product_id=product.id,
                data=StockAdjustRequest(
                    movement_type=MovementType.SHIP,
                    quantity_change=-item.quantity,  # negative = stock leaving
                    note=f"Order {order.id}",
                ),
                adjusted_by=created_by,
                adjusted_by_name=created_by_name,
                commit=False
            )

        # 4. Commit everything atomically
        #    Order + OrderItems + StockMovements + updated product quantities
        #    All in one transaction — all succeed or all roll back
        await self.db.commit()
        await self.db.refresh(order)
        
        # Stock moved and quantities changed — every cached view of them is now wrong.
        # adjust_stock skipped this because we passed commit=False and own the transaction.
        await cache_delete_pattern(ALL_MOVEMENTS_CACHE_PATTERN)
        await cache_delete_pattern(PRODUCTS_CACHE_PATTERN)
        for item, _product in validated_items:
            await cache_delete_pattern(
                STOCK_HISTORY_CACHE_PATTERN.format(product_id=item.product_id)
            )
        
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order.id)
        )
        order = result.scalar_one()

        logger.info(
            "order_created",
            order_id=order.id,
            customer_name=data.customer_name,
            item_count=len(validated_items),
            created_by=created_by,
            created_by_name=created_by_name,
        )

        return order

    # -------------------------------------------------------------------------
    # CANCEL
    # -------------------------------------------------------------------------

    async def cancel_order(
        self,
        order_id: str,
        cancelled_by: str,
        cancelled_by_name: str,
    ) -> Order:
        """
        Cancels a pending order and restores stock for every item.
        Only PENDING orders can be cancelled.
        """

        # 1. Load the order with its items
        order = await self._get_order_or_raise(order_id)

        # 2. Only PENDING orders can be cancelled
        if order.status != OrderStatus.PENDING:
            raise ValueError(
                f"Order {order_id!r} cannot be cancelled. "
                f"Current status: {order.status.value!r}. "
                "Only 'pending' orders can be cancelled."
            )

        # 3. Restore stock for each item via RECEIVE movements
        stock_service = StockService(self.db)

        for item in order.items:
            if item.product_id is None:
                # product was hard-deleted — log and skip, can't restore
                logger.warning(
                    "cancel_order_skip_item",
                    order_id=order_id,
                    product_sku=item.product_sku,
                    reason="product no longer exists in DB",
                )
                continue

            await stock_service.adjust_stock(
                product_id=item.product_id,
                data=StockAdjustRequest(
                    movement_type=MovementType.RECEIVE,
                    quantity_change=item.quantity,  # positive = stock returning
                    note=f"Cancellation of order {order.id}",
                ),
                adjusted_by=cancelled_by,
                adjusted_by_name=cancelled_by_name,
                commit=False
            )

        # 4. Mark the order as cancelled
        order.status = OrderStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(order)
        
        # Stock was restored — same caches are stale as on create.
        await cache_delete_pattern(ALL_MOVEMENTS_CACHE_PATTERN)
        await cache_delete_pattern(PRODUCTS_CACHE_PATTERN)
        for item in order.items:
            if item.product_id is not None:
                await cache_delete_pattern(
                    STOCK_HISTORY_CACHE_PATTERN.format(product_id=item.product_id)
                )

        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order.id)
        )
        
        order = result.scalar_one()
        logger.info(
            "order_cancelled",
            order_id=order_id,
            cancelled_by=cancelled_by,
            cancelled_by_name=cancelled_by_name,
        )

        return order

    # -------------------------------------------------------------------------
    # GET ONE
    # -------------------------------------------------------------------------

    async def get_order(self, order_id: str) -> Order:
        """Fetch a single order by ID. Raises ValueError if not found."""
        return await self._get_order_or_raise(order_id)

    # -------------------------------------------------------------------------
    # LIST paginated
    # -------------------------------------------------------------------------

    async def list_orders(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> OrderListResponse:
        """Returns a paginated list of all orders. Newest first."""

        # 1. Count total orders
        count_result = await self.db.execute(
            select(func.count(Order.id))
        )
        total = count_result.scalar_one()

        # 2. Fetch the page
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        orders = list(result.scalars().all())

        # 3. Pagination maths — same formula as Phase 3 and Phase 4
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return OrderListResponse(
            items=[OrderResponse.model_validate(o) for o in orders],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -------------------------------------------------------------------------
    # PRIVATE HELPER
    # -------------------------------------------------------------------------

    async def _get_order_or_raise(self, order_id: str) -> Order:
        """
        Loads an order with its items eagerly.
        Raises ValueError if not found.
        Prefixed with _ = private, only used inside this service.
        """
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError(f"Order {order_id!r} not found")

        return order