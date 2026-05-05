import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)
from app.services.product_service import ProductService

logger = structlog.get_logger()
router = APIRouter(prefix="/products", tags=["Products"])


# -----------------------------------------------------------------------------
# CREATE
# -----------------------------------------------------------------------------
@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),  # admin only
):
    """Create a new product. Admin only."""
    try:
        product = await ProductService(db).create_product(
            data=data,
            created_by=current_user.id,
        )
        return ProductResponse.model_validate(product)

    except ValueError as e:
        logger.warning("product_create_failed", reason=str(e), sku=data.sku)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


# -----------------------------------------------------------------------------
# LIST (paginated)
# -----------------------------------------------------------------------------
@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(default=False, description="Include soft-deleted products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # any logged-in user
):
    """List all products with pagination. Admins can include inactive."""

    # Non-admins can never see inactive products even if they ask
    if include_inactive and not current_user.is_admin:
        include_inactive = False
        logger.warning(
            "product_list_inactive_denied",
            user_id=current_user.id,
        )

    return await ProductService(db).get_products(
        page=page,
        page_size=page_size,
        include_inactive=include_inactive,
    )


# -----------------------------------------------------------------------------
# GET ONE
# -----------------------------------------------------------------------------
@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),  # any logged-in user
):
    """Fetch a single product by ID."""
    try:
        product = await ProductService(db).get_product(product_id)
        return ProductResponse.model_validate(product)

    except ValueError as e:
        logger.warning("product_get_failed", product_id=product_id, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# -----------------------------------------------------------------------------
# UPDATE
# -----------------------------------------------------------------------------
@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),  # admin only
):
    """Update a product. Admin only. Only sent fields are updated."""
    try:
        product = await ProductService(db).update_product(
            product_id=product_id,
            data=data,
        )
        return ProductResponse.model_validate(product)

    except ValueError as e:
        reason = str(e)
        if "No fields" in reason:
            logger.warning("product_update_empty", product_id=product_id, user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=reason,
            )
        logger.warning("product_update_failed", product_id=product_id, reason=reason)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=reason,
        )


# -----------------------------------------------------------------------------
# DELETE (soft)
# -----------------------------------------------------------------------------
@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # admin only
):
    """Soft delete a product. Admin only."""
    try:
        await ProductService(db).delete_product(product_id)

    except ValueError as e:
        logger.warning("product_delete_failed", product_id=product_id, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )