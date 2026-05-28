from datetime import date, datetime
from decimal import Decimal
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import OrderItem
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.schemas.report import (
    LowStockItem,
    LowStockResponse,
    MovementHistoryItem,
    MovementHistoryResponse,
    StockSummaryItem,
    StockSummaryResponse,
    TopProductItem,
    TopProductsResponse,
)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_summary(self) -> StockSummaryResponse:
        result = await self.db.execute(
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.name.asc())
        )
        products = result.scalars().all()

        items: list[StockSummaryItem] = []
        total_inventory_value = Decimal("0")

        for product in products:
            inventory_value = Decimal(str(product.price)) * Decimal(str(product.quantity))
            total_inventory_value += inventory_value

            items.append(
                StockSummaryItem(
                    id=product.id,
                    name=product.name,
                    sku=product.sku,
                    quantity=product.quantity,
                    price=product.price,
                    inventory_value=inventory_value,
                    is_low_stock=product.is_low_stock,
                    low_stock_threshold=product.low_stock_threshold,
                    is_active=product.is_active,
                )
            )

        return StockSummaryResponse(
            items=items,
            total_inventory_value=total_inventory_value,
            total_products=len(items),
        )

    async def get_low_stock(self) -> LowStockResponse:
        result = await self.db.execute(
            select(Product)
            .where(Product.is_active.is_(True))
            .where(Product.quantity <= Product.low_stock_threshold)
            .order_by(Product.quantity.asc(), Product.name.asc())
        )
        products = result.scalars().all()

        items = [
            LowStockItem(
                id=product.id,
                name=product.name,
                sku=product.sku,
                quantity=product.quantity,
                low_stock_threshold=product.low_stock_threshold,
                is_low_stock=product.is_low_stock,
                is_active=product.is_active,
            )
            for product in products
        ]

        return LowStockResponse(items=items, total=len(items))

    async def get_top_products(self) -> TopProductsResponse:
        result = await self.db.execute(
            select(
                OrderItem.product_sku.label("product_sku"),
                OrderItem.product_name.label("product_name"),
                func.sum(OrderItem.quantity).label("total_quantity"),
                func.count(OrderItem.id).label("total_orders"),
                func.sum(OrderItem.quantity * OrderItem.unit_price).label("total_revenue"),
            )
            .group_by(OrderItem.product_sku, OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc(), OrderItem.product_name.asc())
        )
        rows = result.all()

        items = [
            TopProductItem(
                product_sku=row.product_sku,
                product_name=row.product_name,
                total_quantity=int(row.total_quantity or 0),
                total_orders=int(row.total_orders or 0),
                total_revenue=Decimal(str(row.total_revenue or 0)),
            )
            for row in rows
        ]

        return TopProductsResponse(items=items, total=len(items))

    async def get_movement_history(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> MovementHistoryResponse:
        base_stmt = select(StockMovement).options(selectinload(StockMovement.creator))

        if start_date is not None:
            base_stmt = base_stmt.where(
                StockMovement.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        if end_date is not None:
            base_stmt = base_stmt.where(
                StockMovement.created_at <= datetime.combine(end_date, datetime.max.time())
            )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size

        stmt = (
            base_stmt.order_by(StockMovement.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(stmt)
        movements = result.scalars().all()

        items = [
            MovementHistoryItem(
                id=movement.id,
                product_id=movement.product_id,
                product_sku=movement.product_sku,
                movement_type=movement.movement_type,
                quantity_change=movement.quantity_change,
                quantity_before=movement.quantity_before,
                quantity_after=movement.quantity_after,
                note=movement.note,
                created_by=movement.created_by,
                created_at=movement.created_at,
            )
            for movement in movements
        ]

        total_pages = ceil(total / page_size) if total else 0

        return MovementHistoryResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )