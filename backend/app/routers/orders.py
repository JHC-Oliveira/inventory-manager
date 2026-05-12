import structlog

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderListResponse
from app.services.order_service import OrderService

logger = structlog.get_logger()

router = APIRouter(prefix="/orders", tags=["Orders"])


# -----------------------------------------------------------------------------
# CREATE
# -----------------------------------------------------------------------------

@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any logged-in user
):
    """Create a new order. Any authenticated user can place an order."""
    try:
        order = await OrderService(db).create_order(
            data=data,
            created_by=current_user.id,
            created_by_name=current_user.full_name,
        )
        return OrderResponse.model_validate(order)
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


# -----------------------------------------------------------------------------
# CANCEL
# -----------------------------------------------------------------------------

@router.patch(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),  # admin only
):
    """Cancel a pending order. Admin only. Restores stock automatically."""
    try:
        order = await OrderService(db).cancel_order(
            order_id=order_id,
            cancelled_by=current_user.id,
            cancelled_by_name=current_user.full_name,
        )
        return OrderResponse.model_validate(order)
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            )
        if "cannot be cancelled" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_message,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )


# -----------------------------------------------------------------------------
# GET ONE
# -----------------------------------------------------------------------------

@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),  # any logged-in user
):
    """Fetch a single order by ID. Any authenticated user."""
    try:
        order = await OrderService(db).get_order(order_id)
        return OrderResponse.model_validate(order)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# -----------------------------------------------------------------------------
# LIST paginated
# -----------------------------------------------------------------------------

@router.get(
    "",
    response_model=OrderListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_orders(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),  # any logged-in user
):
    """List all orders with pagination. Any authenticated user."""
    return await OrderService(db).list_orders(
        page=page,
        page_size=page_size,
    )