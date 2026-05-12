import math
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.schemas.stock_movement import StockAdjustRequest, StockMovementListResponse, StockMovementResponse
from app.utils.rabbitmq import publish_low_stock_alert

logger = structlog.get_logger()


class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def adjust_stock(
        self,
        product_id: str,
        data: StockAdjustRequest,
        adjusted_by: str,
        adjusted_by_name: str,
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
            product_sku=product.sku,   # ← snapshot at creation time
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

        # 6. Commit both changes atomically
        await self.db.commit()
        await self.db.refresh(movement)

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

        # 7. Publish low stock alert AFTER commit — fire and forget
        if product.is_low_stock:
            await publish_low_stock_alert(
                product_id=product_id,
                sku=product.sku,
                current_quantity=quantity_after,
                threshold=product.low_stock_threshold,
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

        return StockMovementListResponse(
            items=[StockMovementResponse.model_validate(m) for m in movements],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 1,
        )