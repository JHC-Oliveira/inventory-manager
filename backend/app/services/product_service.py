import math
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductListResponse, ProductResponse

logger = structlog.get_logger()


class ProductService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------
    async def create_product(self, data: ProductCreate, created_by: str) -> Product:
        """Create a new product. Raises ValueError if SKU already exists."""

        # 1. Check SKU uniqueness
        existing = await self.db.execute(
            select(Product).where(Product.sku == data.sku)
        )
        if existing.scalar_one_or_none():
            logger.warning(             # ← warning, not info
            "product_sku_conflict",
            sku=data.sku,
            created_by=created_by  # who tried
        )
            raise ValueError(f"A product with SKU '{data.sku}' already exists")

        # 2. Build the product object
        product = Product(
            **data.model_dump(),
            created_by=created_by,
        )
        self.db.add(product)
        await self.db.flush()   # get the generated id
        await self.db.commit()  # persist to DB

        logger.info("product_created", product_id=product.id, sku=product.sku, created_by=created_by)

        return product

    # -------------------------------------------------------------------------
    # READ ONE
    # -------------------------------------------------------------------------
    async def get_product(self, product_id: str) -> Product:
        """Fetch a single active product by ID. Raises ValueError if not found."""

        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active
            )
        )
        product = result.scalar_one_or_none()

        if not product:
            logger.warning(             #warning
            "product_not_found",
            product_id=product_id
        )
            raise ValueError(f"Product '{product_id}' not found")

        return product

    # -------------------------------------------------------------------------
    # READ MANY (paginated)
    # -------------------------------------------------------------------------
    async def get_products(
        self,
        page: int = 1,
        page_size: int = 10,
        include_inactive: bool = False,
    ) -> ProductListResponse:
        """Return a paginated list of products."""

        # 1. Base query — filter inactive unless admin requests them
        query = select(Product)
        if not include_inactive:
            query = query.where(Product.is_active)

        # 2. Count total matching products (for pagination maths)
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # 3. Fetch the actual page
        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Product.created_at.desc())
                 .offset(offset)
                 .limit(page_size)
        )
        products = result.scalars().all()

        # 4. Calculate total pages
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return ProductListResponse(
            items=[ProductResponse.model_validate(p) for p in products],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -------------------------------------------------------------------------
    # UPDATE
    # -------------------------------------------------------------------------
    async def update_product(self, product_id: str, data: ProductUpdate) -> Product:
        """Update only the fields the client explicitly sent."""

        # 1. Find the product
        product = await self.get_product(product_id)

        # 2. Only update fields that were actually sent
        # exclude_unset=True is the fix for the Optional ambiguity we discussed
        changes = data.model_dump(exclude_unset=True)

        if not changes:
            logger.warning(             
            "product_update_empty",
            product_id=product_id  # which product is empty?
        )
            raise ValueError("No fields provided to update")

        for field, value in changes.items():
            setattr(product, field, value)

        await self.db.commit()

        logger.info("product_updated", product_id=product.id, changes=list(changes.keys()))

        return product

    # -------------------------------------------------------------------------
    # DELETE (soft)
    # -------------------------------------------------------------------------
    async def delete_product(self, product_id: str) -> None:
        """Soft delete — sets is_active=False, never destroys data."""

        product = await self.get_product(product_id)
        product.is_active = False
        await self.db.commit()

        logger.info("product_deleted", product_id=product.id, sku=product.sku)