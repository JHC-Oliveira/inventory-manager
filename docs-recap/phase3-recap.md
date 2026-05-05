# Phase 3 Recap — Products & Inventory

## What Phase 3 Was About

Phase 2 built the authentication system — users can register, log in, and prove their identity with tokens. Phase 3 builds the first real business feature of the Inventory Manager: **a complete product management system**.

By the end of Phase 3, admins can create, update, and delete products, any logged-in user can browse the catalogue with pagination, and the system enforces stock tracking with low stock alerts — with soft deletes ensuring data is never permanently destroyed.

---

## The Big Picture — How Products Work in This App

Before looking at individual steps, here is the complete request flow:

```
CREATE PRODUCT
  Client ──POST /products──────────► Server
         Authorization: Bearer ...   1. get_current_admin (is_admin=True check)
                                     2. Validate input (ProductCreate schema)
                                     3. Check SKU doesn't already exist
                                     4. Save product to PostgreSQL
                                     5. Log the creation
                                    ◄── 201 + ProductResponse

LIST PRODUCTS
  Client ──GET /products?page=1──────► Server
         Authorization: Bearer ...    1. get_current_user (any logged-in user)
                                      2. Query DB with pagination
                                      3. Count total matching products
                                      4. Calculate total_pages
                                     ◄── 200 + ProductListResponse

GET ONE PRODUCT
  Client ──GET /products/{id}─────────► Server
         Authorization: Bearer ...     1. get_current_user (any logged-in user)
                                       2. Query by ID where is_active=True
                                      ◄── 200 + ProductResponse (or 404)

UPDATE PRODUCT
  Client ──PUT /products/{id}─────────► Server
         Authorization: Bearer ...     1. get_current_admin (is_admin=True check)
         { "price": 39.99 }            2. Validate input (ProductUpdate schema)
                                       3. Apply only fields that were sent
                                       4. Commit changes
                                      ◄── 200 + ProductResponse

DELETE PRODUCT
  Client ──DELETE /products/{id}──────► Server
         Authorization: Bearer ...     1. get_current_admin (is_admin=True check)
                                       2. Set is_active = False (soft delete)
                                       3. Commit
                                      ◄── 204 No Content
```

**Key insight:** Admins write, users read. Every mutation (create, update, delete) requires `is_admin=True`. Listing and fetching only require a valid token. Deleted products set `is_active = False` — the row stays in the database forever, invisible to the API.

---

## Step 1 — Planning the Model and Endpoints

Before writing any code, the table was designed:

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Unguessable primary key |
| `sku` | String (unique) | Stock Keeping Unit — permanent product identifier |
| `name` | String | Product display name |
| `description` | Text (nullable) | Optional longer description |
| `price` | Numeric(10,2) | Exact decimal — never float |
| `quantity` | Integer | Current stock count |
| `low_stock_threshold` | Integer | Alert level — default 10 |
| `is_active` | Boolean | Soft delete flag |
| `created_by` | UUID (FK → users) | Which admin created it |
| `created_at` | DateTime (UTC) | Creation timestamp |
| `updated_at` | DateTime (UTC) | Auto-updates on every change |

And the five endpoints planned upfront:

```
POST   /products          → Create (admin only)
GET    /products          → List paginated (any logged-in user)
GET    /products/{id}     → Get one (any logged-in user)
PUT    /products/{id}     → Update (admin only)
DELETE /products/{id}     → Soft delete (admin only)
```

**Professional habit:** Model your data and API surface before touching code. Know exactly what you're building and why every field exists.

---

## Step 2 — The Product Model (`models/product.py`)

```python
class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ..., onupdate=...)

    creator: Mapped["User"] = relationship("User", backref="products")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.low_stock_threshold
```

**Design decisions explained:**

- **`Numeric(10, 2)` instead of `Float` for price** — Float is an approximation. `29.99` stored as a float can become `29.989999999999998` in the database. `Numeric` stores exact decimals — mandatory for any money value.

- **`ondelete="SET NULL"` on `created_by`** — If the admin who created a product is later deleted, the product must survive. `SET NULL` sets `created_by` to `None` on the product row. Using `CASCADE` instead would delete the product too — the wrong behaviour.

- **`is_low_stock` as a `@property`** — Never stored, always calculated:
  ```
  quantity = 3, low_stock_threshold = 10  →  is_low_stock = True
  quantity = 50, low_stock_threshold = 10 →  is_low_stock = False
  ```
  No extra column in the DB. `from_attributes=True` in `ProductResponse` automatically reads Python properties.

- **`TYPE_CHECKING` for the User import** — The product model needs to reference `User` for the relationship, but importing User directly creates a circular import (user imports nothing, product imports user — fine, but if user ever imports product it breaks). The fix:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from app.models.user import User   # only runs for Pylance, not at runtime
  ```
  SQLAlchemy resolves the relationship from the string `"User"` lazily at runtime.

---

## Step 3 — Product Schemas (`schemas/product.py`)

Four schemas, each with a specific job:

| Schema | Direction | Purpose |
|---|---|---|
| `ProductCreate` | IN | Validate new product data from client |
| `ProductUpdate` | IN | Validate partial update — all fields optional |
| `ProductResponse` | OUT | Shape of product data returned to client |
| `ProductListResponse` | OUT | Paginated list wrapper |

**`ProductCreate` validator — SKU normalisation:**

```python
@field_validator("sku")
def sku_uppercase(cls, v):
    return v.upper().strip()   # "tshirt-blu-l" → "TSHIRT-BLU-L"
```

SKUs are always stored uppercase regardless of what the client sends. This prevents `"TSHIRT"` and `"tshirt"` coexisting as duplicate products because of capitalisation.

**The `Optional` + `exclude_unset` pattern in `ProductUpdate`:**

This was an important edge case discovered during planning:

```
Problem: Admin wants to CLEAR the description → sends { "description": null }

If we use  exclude_none=True  → strips ALL None values → description never cleared  ❌
If we use  exclude_unset=True → strips only fields NOT sent at all

Admin sends { "price": 39.99 }
  → exclude_unset → { "price": 39.99 }                        ✅ description untouched

Admin sends { "price": 39.99, "description": null }
  → exclude_unset → { "price": 39.99, "description": None }   ✅ description cleared
```

`Optional` in `ProductUpdate` means **"not required to send"**, not **"will be set to NULL"**. The distinction is handled entirely by `exclude_unset=True` in the service.

**`ProductListResponse` — pagination wrapper:**

```python
class ProductListResponse(BaseModel):
    items: list[ProductResponse]   # products on this page
    total: int                     # total matching records in DB (e.g. 47)
    page: int                      # current page (e.g. 2)
    page_size: int                 # records per page (e.g. 10)
    total_pages: int               # ceil(total / page_size) = 5
```

Never return all records at once. Pagination protects the database from being queried for thousands of rows in a single request.

---

## Step 4 — Product Service (`services/product_service.py`)

The service is where all business logic lives — completely separate from HTTP.

```python
class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
```

The DB session is injected from the router — the service never creates its own session.

**Five methods and the decisions behind them:**

**`create_product` — manual SKU check before insert:**
```python
existing = await self.db.execute(select(Product).where(Product.sku == sku))
if existing.scalar_one_or_none():
    raise ValueError(f"Product with SKU '{sku}' already exists")
```
The DB has a `unique=True` constraint on `sku`, which would catch duplicates anyway. But a DB constraint raises a cryptic `IntegrityError`. A manual check raises a clean `ValueError` that the router catches and converts to a descriptive `409 Conflict`.

**`get_products` — pagination maths:**
```python
offset = (page - 1) * page_size
# page=1 → offset=0  → rows 1-10
# page=2 → offset=10 → rows 11-20

total_pages = math.ceil(total / page_size)
# 47 products / 10 per page = 4.7 → ceil → 5 pages ✅
# Without ceil: int(4.7) = 4, last 7 products unreachable ❌
```

**`update_product` — `exclude_unset` in action:**
```python
changes = data.model_dump(exclude_unset=True)
for field, value in changes.items():
    setattr(product, field, value)
```
Only fields explicitly sent by the client are touched. Everything else stays exactly as it was.

**`delete_product` — soft delete:**
```python
product.is_active = False   # never destroyed
await self.db.commit()
```
```
HARD DELETE: row gone forever → order history breaks, audit trail lost  ❌
SOFT DELETE: is_active=False → history intact, reversible, auditable   ✅
```

**Logging pattern established in Phase 3:**
```python
logger.info()    → something succeeded
logger.warning() → bad input, suspicious behaviour, empty update body
logger.error()   → unexpected failure
```
Every service method logs success. Every failure path logs a warning with context (`product_id`, reason, `user_id`).

---

## Step 5 — Product Router (`routers/product.py`)

The router's only job: receive HTTP, call the service, return HTTP. No DB queries, no business rules.

**Authentication level per endpoint:**
```
POST   /products      → get_current_admin → is_admin=True only
GET    /products      → get_current_user  → any logged-in user
GET    /products/{id} → get_current_user  → any logged-in user
PUT    /products/{id} → get_current_admin → is_admin=True only
DELETE /products/{id} → get_current_admin → is_admin=True only
```

**Query parameters on the list endpoint:**
```python
page: int = Query(default=1, ge=1)
page_size: int = Query(default=10, ge=1, le=100)  # le=100 prevents abuse
include_inactive: bool = Query(default=False)
```
`le=100` on `page_size` prevents a client requesting 10,000 products at once and hammering the database.

**Non-admin inactive guard:**
```python
if include_inactive and not current_user.is_admin:
    include_inactive = False
    logger.warning("product_list_inactive_denied", user_id=current_user.id)
```
Regular users requesting inactive products are silently overridden — they get active-only results. The warning in logs lets you spot API probing.

**`ValueError` → `HTTPException` translation:**
```python
try:
    product = await ProductService(db).create_product(...)
except ValueError as e:
    raise HTTPException(status_code=409, detail=str(e))
```
The service raises plain Python errors with no HTTP knowledge. The router translates them into correct status codes. This keeps the service reusable in any context (scripts, background jobs, tests).

**`204 No Content` on delete:**
```python
@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
```
REST convention — `DELETE` returns no body, just confirmation the operation succeeded.

---

## Step 6 — Wire and Migrate

**`models/__init__.py`** — registered the new model so Alembic can see it:
```python
from app.models.product import Product  # noqa: F401
```

**`main.py`** — wired the router:
```python
from app.routers.product import router as product_router
app.include_router(product_router)
```

**Alembic migration:**
```bash
docker compose exec api alembic revision --autogenerate -m "add products table"
docker compose exec api alembic upgrade head
```

Alembic compares `Base.metadata` (the model definitions) against the live DB schema and generates the SQL to make them match. This is why the `import app.models` line in `alembic/env.py` is critical — without it Alembic sees an empty schema and generates nothing.

---

## Step 7 — Tests (`tests/test_products.py`)

16 tests covering every rule:

| Test | What it proves |
|---|---|
| `test_admin_can_create_product` | 201, correct data, `is_low_stock` calculated correctly |
| `test_regular_user_cannot_create_product` | 403 for non-admins |
| `test_unauthenticated_cannot_create_product` | 401 without token |
| `test_duplicate_sku_rejected` | 409 on duplicate SKU |
| `test_sku_is_stored_uppercase` | `@field_validator` normalises lowercase input |
| `test_logged_in_user_can_list_products` | 200, correct total |
| `test_unauthenticated_cannot_list_products` | 401 without token |
| `test_pagination_works` | `total_pages` calculated correctly |
| `test_get_product_by_id` | 200 with correct data |
| `test_get_nonexistent_product_returns_404` | 404 for unknown ID |
| `test_admin_can_update_product` | Only sent fields changed, others untouched |
| `test_empty_update_rejected` | 422 for empty `{}` |
| `test_regular_user_cannot_update_product` | 403 for non-admins |
| `test_admin_can_delete_product` | 204 |
| `test_deleted_product_not_in_list` | Soft deleted product invisible in list |
| `test_deleted_product_returns_404` | Soft deleted product invisible by ID |

**Two new fixtures added to `conftest.py`:**

```python
@pytest_asyncio.fixture
async def user_token(client) -> str:
    # Registers a regular user, logs in, returns their access token

@pytest_asyncio.fixture
async def admin_token(client) -> str:
    # Registers a user, flips is_admin=True directly in DB, returns token
```

**Why flip `is_admin` directly in the DB?**

There is no "make me admin" API endpoint — that would be a serious security hole. In tests the `is_admin` flag is flipped directly via a SQL UPDATE to simulate a state that would be set by a superuser or deployment script in production:

```python
db_generator = app.dependency_overrides[real_get_db]   # direct key access
async for session in db_generator():
    await session.execute(
        update(User)
        .where(User.email == "admin@example.com")
        .values(is_admin=True)
    )
    await session.commit()
    break
```

Note: `app.dependency_overrides[real_get_db]` uses direct key access (`[]`) not `.get()`. `.get()` returns `Optional` and Pylance warns that the result could be `None` and therefore not callable. Direct key access tells Pylance the value is guaranteed to exist — which it is, because the `client` fixture always sets the override before `admin_token` runs.

**The `{**PRODUCT_PAYLOAD, "sku": "DIFFERENT"}` pattern:**

```python
PRODUCT_PAYLOAD = {
    "name": "Test T-Shirt", "sku": "TSHIRT-BLU-L", "price": "29.99", ...
}

# Override one field, keep all the rest:
{**PRODUCT_PAYLOAD, "sku": "TSHIRT-RED-L"}
```

Define the base payload once at the top, spread and override per test. No repetition, no drift between tests.

---

## Bugs Fixed Along the Way

| Bug | Cause | Fix |
|---|---|---|
| Pylance `reportOptionalCall` on `db_override()` | `.get()` returns `Optional`, Pylance can't guarantee it's callable | Switched to direct `[]` key access |

---

## Phase 3 Security Habits Established

1. **Admin-only mutations** — create, update, delete all require `is_admin=True`
2. **Silent override on scope creep** — non-admins requesting inactive products get active-only results, logged as a warning
3. **Manual uniqueness check** — clean `409 Conflict` instead of a cryptic DB `IntegrityError`
4. **Soft delete everywhere** — data is never destroyed, always recoverable and auditable
5. **Pagination enforced** — `le=100` prevents unbounded queries
6. **Logging on every path** — success, warnings, and errors all captured with structured context

---

## What's Next — Phase 4

Phase 4 will build **stock management** — dedicated endpoints for adjusting stock levels (receive stock, ship stock), stock movement history, and the low stock alert system using RabbitMQ to publish events when quantity drops below the threshold.
