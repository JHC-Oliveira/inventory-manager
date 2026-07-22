import math
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.product import Product
from app.models.stock_movement import StockMovement, MovementType
from app.schemas.stock_movement import StockAdjustRequest, StockMovementListResponse, StockMovementResponse
from app.utils.rabbitmq import publish_low_stock_alert
from app.utils.redis_client import cache_get, cache_set, cache_delete_pattern
from app.services.product_service import PRODUCTS_CACHE_PATTERN


logger = structlog.get_logger()

STOCK_HISTORY_CACHE_TTL = 60
STOCK_HISTORY_CACHE_PATTERN = "stock:history:{product_id}:*"
ALL_MOVEMENTS_CACHE_PATTERN = "stock:movements:*"


class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def adjust_stock(
        self,
        product_id: str,
        data: StockAdjustRequest,
        adjusted_by: str,
        adjusted_by_name: str = "",
        commit: bool = True, 
    ) -> StockMovement:
        """
        Adjusts the stock for a product.
        Creates a StockMovement record, updates product.quantity,
        and publishes a RabbitMQ alert if stock drops to or below threshold.
        """
        # 1. Load the product
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active,
            )
        )
        product = result.scalar_one_or_none()

        if product is None:
            logger.warning(
                "stock_adjust_product_not_found",
                product_id=product_id,
                adjusted_by=adjusted_by,
            )
            raise ValueError(f"Product '{product_id}' not found")

        # 2. Calculate quantities
        quantity_before = product.quantity
        quantity_after = quantity_before + data.quantity_change

        # 3. Prevent stock going below zero
        if quantity_after < 0:
            logger.warning(
                "stock_adjust_insufficient_stock",
                product_id=product_id,
                sku=product.sku,
                quantity_before=quantity_before,
                quantity_change=data.quantity_change,
                adjusted_by=adjusted_by,
                adjusted_by_name=adjusted_by_name
            )
            raise ValueError(
                f"Insufficient stock. Current: {quantity_before}, "
                f"change: {data.quantity_change}, result would be: {quantity_after}"
            )

        # 4. Create the movement record — BEFORE updating the product
        movement = StockMovement(
            product_id=product_id,
            product_sku=product.sku,   # snapshot at creation time
            movement_type=data.movement_type,
            quantity_change=data.quantity_change,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            note=data.note,
            created_by=adjusted_by,
        )
        self.db.add(movement)

        # 5. Update the product quantity
        product.quantity = quantity_after

        # 6. Commit OR just flush — caller decides
        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
            
            await cache_delete_pattern(
                STOCK_HISTORY_CACHE_PATTERN.format(product_id=product_id),
            )
            
            await cache_delete_pattern(PRODUCTS_CACHE_PATTERN)
            await cache_delete_pattern(ALL_MOVEMENTS_CACHE_PATTERN)
                        
            logger.info(
                "stock_history_cache_invalidated",
                pattern=STOCK_HISTORY_CACHE_PATTERN.format(product_id=product_id),
                reason="stock_adjusted",
                product_id=product_id,
            )
            
            # 7. Publish low stock alert AFTER commit — fire and forget
            if product.is_low_stock:
                await publish_low_stock_alert(
                    product_id=product_id,
                    sku=product.sku,
                    current_quantity=quantity_after,
                    threshold=product.low_stock_threshold,
            )
        else:
            await self.db.flush()   # write to DB but don't close transaction

        logger.info(
            "stock_adjusted",
            product_id=product_id,
            sku=product.sku,
            movement_type=data.movement_type.value,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            quantity_change=data.quantity_change,
            adjusted_by=adjusted_by,
            adjusted_by_name=adjusted_by_name
        )

        return movement

    async def get_movement_history(
        self,
        product_id: str,
        page: int = 1,
        page_size: int = 10,
    ) -> StockMovementListResponse:
        """
        Returns paginated movement history for a product.
        Most recent movements first.
        """
        cache_key = f"stock:history:{product_id}:{page}:{page_size}"

        cached_data = await cache_get(cache_key)
        
        if cached_data is not None:
            logger.info(
                "stock_history_cache_hit",
                cache_key=cache_key,
                product_id=product_id,
                page=page,
                page_size=page_size,
            )
            return StockMovementListResponse(**cached_data)
        
        logger.info(
            "stock_history_cache_miss",
            cache_key=cache_key,
            product_id=product_id,
            page=page,
            page_size=page_size,
        )
        
        # Verify product exists
        product_result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        if product_result.scalar_one_or_none() is None:
            raise ValueError(f"Product '{product_id}' not found")

        # Count total movements
        count_result = await self.db.execute(
            select(func.count(StockMovement.id)).where(
                StockMovement.product_id == product_id
            )
        )
        total = count_result.scalar_one()

        # Fetch paginated movements — newest first
        offset = (page - 1) * page_size
        movements_result = await self.db.execute(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        movements = list(movements_result.scalars().all())

        response = StockMovementListResponse(
            items=[StockMovementResponse.model_validate(m) for m in movements],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 1,
        )
        
        await cache_set(
            cache_key,
            response.model_dump(mode="json"),
            STOCK_HISTORY_CACHE_TTL,
        )

        logger.info(
            "stock_history_cache_set",
            cache_key=cache_key,
            ttl=STOCK_HISTORY_CACHE_TTL,
            item_count=len(response.items),
            product_id=product_id,
        )       
        
        return response

    async def get_all_movements(
        self,
        page: int = 1,
        page_size: int = 10,
        movement_type: MovementType | None = None,
    ) -> StockMovementListResponse:
        """
        Returns paginated movement history across all products.
        Most recent movements first. Optionally filtered by movement_type.
        """
        cache_key = f"stock:movements:{page}:{page_size}:{movement_type}"

        cached_data = await cache_get(cache_key)
        if cached_data is not None:
            logger.info("stock_all_movements_cache_hit", cache_key=cache_key)
            return StockMovementListResponse(**cached_data)

        query = select(StockMovement)
        if movement_type is not None:
            query = query.where(StockMovement.movement_type == movement_type)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        movements_result = await self.db.execute(
            query.order_by(StockMovement.created_at.desc())
                 .offset(offset)
                 .limit(page_size)
        )
        movements = list(movements_result.scalars().all())

        response = StockMovementListResponse(
            items=[StockMovementResponse.model_validate(m) for m in movements],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 1,
        )

        await cache_set(cache_key, response.model_dump(mode="json"), STOCK_HISTORY_CACHE_TTL)
        logger.info("stock_all_movements_cache_set", cache_key=cache_key, item_count=len(response.items))

        return response

    