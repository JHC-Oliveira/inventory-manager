from datetime import date

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.stock_movement import MovementType
from app.models.user import User
from app.schemas.stock_movement import (
    StockAdjustRequest,
    StockMovementListResponse,
    StockMovementResponse,
)
from app.services.stock_service import StockService

logger = structlog.get_logger()

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.post(
    "/{product_id}/adjust",
    response_model=StockMovementResponse,
    status_code=status.HTTP_200_OK,
)
async def adjust_stock(
    product_id: str,
    data: StockAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Adjust stock for a product.
    Requires admin. Creates a permanent movement record.
    Publishes a RabbitMQ alert if stock drops to or below threshold.
    """
    try:
        movement = await StockService(db).adjust_stock(
            product_id=product_id,
            data=data,
            adjusted_by=current_user.id,
            adjusted_by_name=current_user.full_name
        )
        return StockMovementResponse.model_validate(movement)


    except ValueError as e:
        error_message = str(e)

        if "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            )
        if "insufficient stock" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )


@router.get(
    "/{product_id}/history",
    response_model=StockMovementListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movement_history(
    product_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns paginated movement history for a product.
    Any logged-in user can view history.
    Most recent movements first.
    """
    try:
        return await StockService(db).get_movement_history(
            product_id=product_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
        
@router.get(
    "/movements",
    response_model=StockMovementListResponse,
    status_code=status.HTTP_200_OK,
)

async def get_all_movements(
    movement_type: MovementType | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns paginated movement history across all products.
    Any logged-in user can view.
    Optional filters: movement_type and/or a date range.
    """
    return await StockService(db).get_all_movements(
        page=page,
        page_size=page_size,
        movement_type=movement_type,
        start_date=start_date,
        end_date=end_date,
    )