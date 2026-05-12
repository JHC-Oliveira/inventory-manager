# Phase 5 Recap — Orders & Order Items

## What came before — what this phase adds — what you can do by the end

Phase 4 gave us a full audit trail. Every stock change creates a permanent `StockMovement` record — who changed it, when, by how much, before and after. But those movements were all created manually by an admin calling `POST /stock/{product_id}/adjust`.

Phase 5 connects orders to stock automatically. When a customer places an order, every product in that order triggers a `SHIP` movement without the admin doing anything. When an order is cancelled, every product's stock is restored with a `RECEIVE` movement. The audit trail from Phase 4 fills in automatically as a side effect of order operations.

By the end of this phase you can:
- Create an order with multiple line items
- Have stock automatically reduced on order creation
- Cancel an order and have stock automatically restored
- View order history with full item breakdown including price snapshots
- Enforce business rules: no over-ordering, no double-cancelling, atomic rollback on partial failure

---

## Phase 5 Files Built

```
backend/
  app/
    models/
      order.py              ← Order + OrderItem models
    schemas/
      order.py              ← Request/response shapes
    services/
      order_service.py      ← Business logic (calls StockService internally)
    routers/
      orders.py             ← HTTP endpoints
  tests/
    test_orders.py          ← 25 tests

Files updated:
  app/models/__init__.py         ← register Order, OrderItem
  app/services/stock_service.py  ← added adjusted_by_name, commit flag, product_sku snapshot
  app/schemas/stock_movement.py  ← product_id Optional, product_sku added, created_by_name removed
  app/main.py                    ← wire orders router
  alembic/versions/              ← new migration for orders, order_items, stock fixes
```

---

## The Phase 5 Plan — Step by Step

```
Step 1  Order + OrderItem models
Step 2  Order schemas
Step 3  Order service
Step 4  Order router
Step 5  Wire into main.py + migrate
Step 6  Tests
```

---

## The Big Picture — How an Order Flows

```
CREATE ORDER
─────────────────────────────────────────────────────────────
Client   POST /orders
         Authorization: Bearer <user_token>
         Body: { customer_name, items: [{product_id, quantity}] }

Server
  1. get_current_user        verify JWT, any logged-in user
  2. OrderCreate schema      validate body shape
  3. PRE-FLIGHT CHECK — validate ALL items BEFORE touching data
     For each item:
       a. SELECT product WHERE id = ? AND is_active = true
          → 404 if not found or inactive
       b. Check product.quantity >= requested quantity
          → 409 if insufficient
  4. INSERT Order (status: PENDING)
     flush() → get order.id
  5. For each item:
     a. INSERT OrderItem (locks in price snapshot at this moment)
     b. StockService.adjust_stock(SHIP, commit=False)
        → creates StockMovement, updates product.quantity
        → does NOT commit yet (flush only)
  6. db.commit() — ONE atomic commit
     Order + OrderItems + StockMovements + product quantities
     ALL saved together or ALL rolled back
  7. Re-fetch order with selectinload(items)
  8. Return 201 OrderResponse

CANCEL ORDER
─────────────────────────────────────────────────────────────
Client   PATCH /orders/{order_id}/cancel
         Authorization: Bearer <admin_token>

Server
  1. get_current_admin       JWT + isadmin check
  2. Load order + items      selectinload
  3. Check status == PENDING → 409 if already CANCELLED or FULFILLED
  4. For each item:
     a. Skip if product_id is None (hard-deleted product — log warning)
     b. StockService.adjust_stock(RECEIVE, commit=False)
        → creates StockMovement, restores product.quantity
  5. order.status = CANCELLED
  6. db.commit() — ONE atomic commit
  7. Re-fetch order with selectinload(items)
  8. Return 200 OrderResponse

GET ONE ORDER
─────────────────────────────────────────────────────────────
Client   GET /orders/{order_id}
         Authorization: Bearer <any user>
Server   selectinload(items) → return OrderResponse

LIST ORDERS
─────────────────────────────────────────────────────────────
Client   GET /orders?page=1&page_size=10
         Authorization: Bearer <any user>
Server   COUNT total → SELECT with selectinload → return OrderListResponse
```

**Key insight:** `StockService` from Phase 4 does all the stock logic. `OrderService` calls it as a dependency. The two are decoupled — orders don't know how stock works, stock doesn't know about orders. The `commit=False` flag (added in this phase) lets `OrderService` own the single transaction.

---

## Step 1 — Order + OrderItem Models
### `backend/app/models/order.py`

```python
class OrderStatus(PyEnum):
    PENDING   = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"

class Order(Base):
    __tablename__ = "orders"

    id:            Mapped[str]         # UUID primary key
    customer_name: Mapped[str]
    status:        Mapped[OrderStatus] # default PENDING
    created_by:    Mapped[str | None]  # FK users.id, ON DELETE SET NULL
    created_at:    Mapped[datetime]
    updated_at:    Mapped[datetime]

    items:   Mapped[list["OrderItem"]] # relationship, cascade all/delete-orphan
    creator: Mapped["User"]            # relationship

class OrderItem(Base):
    __tablename__ = "order_items"

    id:           Mapped[str]          # UUID primary key
    order_id:     Mapped[str]          # FK orders.id, ON DELETE CASCADE
    product_id:   Mapped[str | None]   # FK products.id, ON DELETE SET NULL
    product_name: Mapped[str]          # snapshot — never changes after order
    product_sku:  Mapped[str]          # snapshot
    quantity:     Mapped[int]
    unit_price:   Mapped[Decimal]      # snapshot — price at time of order
    created_at:   Mapped[datetime]

    @property
    def subtotal(self) -> Decimal:
        return Decimal(str(self.quantity)) * self.unit_price
```

### Why the decisions were made this way

- **`product_id` is nullable on `OrderItem`** — if a product is hard-deleted, the order item still exists. `ON DELETE SET NULL` means the order history survives. The snapshot columns (`product_name`, `product_sku`, `unit_price`) preserve all the information you need even after the product is gone.

- **`product_name`, `product_sku`, `unit_price` are snapshots** — copied at order creation time and never updated. If the product's price changes tomorrow, yesterday's orders still show what the customer actually paid. This is how every real e-commerce system works.

- **`subtotal` is a computed property, not a column** — it's always `quantity × unit_price`. Storing it as a column would create a risk of it getting out of sync. We compute it on demand and never write it to the database.

- **`cascade="all, delete-orphan"` on `items`** — if an Order is deleted, all its OrderItems are deleted automatically. An OrderItem can never exist without a parent Order.

- **`OrderStatus` values are uppercase** — consistent with `MovementType` (`SHIP`, `RECEIVE`, `ADJUST`). All enums in this project use uppercase values.

---

## Step 2 — Order Schemas
### `backend/app/schemas/order.py`

```python
class OrderItemCreate(BaseModel):
    product_id: str
    quantity:   int  # must be > 0

class OrderCreate(BaseModel):
    customer_name: str
    items: list[OrderItemCreate]  # min_length=1, no duplicate product_ids

class OrderItemResponse(BaseModel):
    id:           str
    product_id:   Optional[str]
    product_name: str
    product_sku:  str
    quantity:     int
    unit_price:   Decimal
    subtotal:     Decimal          # computed property from model
    model_config = {"from_attributes": True}

class OrderResponse(BaseModel):
    id:            str
    customer_name: str
    status:        str
    created_by:    Optional[str]
    created_at:    datetime
    updated_at:    datetime
    items:         list[OrderItemResponse]
    model_config = {"from_attributes": True}

class OrderListResponse(BaseModel):
    items:       list[OrderResponse]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
```

### Why the decisions were made this way

- **`min_length=1` on `items`** — an order with zero items is not an order. Pydantic rejects it at the schema level with 422 before the service even runs.

- **`model_validator` to reject duplicate `product_id`s** — sending the same product twice in one order is always a client mistake. Caught at schema level with 422.

- **`subtotal` in `OrderItemResponse`** — it's a computed property on the model. Pydantic reads it via `from_attributes=True` the same way it reads a real column. The client gets the calculated value without us ever storing it in the database.

---

## Step 3 — Order Service
### `backend/app/services/order_service.py`

```
create_order(data, created_by, created_by_name) → Order
  1. Pre-flight: validate ALL products before touching anything
  2. INSERT Order + flush() to get order.id
  3. For each item:
       INSERT OrderItem (snapshot)
       StockService.adjust_stock(SHIP, commit=False)
  4. ONE db.commit() — atomic
  5. Re-fetch with selectinload(Order.items)

cancel_order(order_id, cancelled_by, cancelled_by_name) → Order
  1. _get_order_or_raise (loads with selectinload)
  2. Check status == PENDING → 409 if not
  3. For each item (skip if product_id is None):
       StockService.adjust_stock(RECEIVE, commit=False)
  4. order.status = CANCELLED
  5. ONE db.commit()
  6. Re-fetch with selectinload(Order.items)

get_order(order_id) → Order
  → _get_order_or_raise

list_orders(page, page_size) → OrderListResponse
  → COUNT → SELECT with selectinload → paginate

_get_order_or_raise(order_id) → Order   [private]
  → SELECT with selectinload(Order.items)
  → ValueError if not found
```

### Why the decisions were made this way

- **Pre-flight validation before any writes** — we check all products and all stock levels BEFORE creating the Order or any OrderItems. If item 3 of 5 fails, nothing has been written yet. No partial orders, no cleanup needed.

- **`commit=False` on every `StockService.adjust_stock` call** — this is the most important decision in Phase 5. The stock service normally commits after every adjustment. Inside `create_order`, we need all adjustments to be part of ONE transaction. The `commit=False` flag tells the stock service to `flush()` instead of `commit()`. The single `db.commit()` at the end commits everything atomically.

- **Re-fetch after commit with `selectinload`** — after `db.commit()`, SQLAlchemy expires all loaded attributes. The relationship `order.items` becomes unavailable. We immediately re-fetch the order with a fresh SELECT that eagerly loads items. This is the object we return to the router.

- **`_get_order_or_raise` always uses `selectinload`** — any time we load an order for GET, cancel, or internal use, items are loaded in the same query. SQLAlchemy async cannot lazy-load relationships (it would deadlock the event loop), so we always load eagerly.

- **Cancellation skips `product_id is None` items** — if a product was hard-deleted after the order was placed, the `OrderItem.product_id` is NULL (because of `ON DELETE SET NULL`). We can't restore stock to a product that doesn't exist. We log a warning and skip it.

---

## Step 4 — Order Router
### `backend/app/routers/orders.py`

```
router = APIRouter(prefix="/orders", tags=["Orders"])

POST   ""                    → create_order   (any user, 201)
PATCH  "/{order_id}/cancel"  → cancel_order   (admin only, 200)
GET    "/{order_id}"         → get_order      (any user, 200)
GET    ""                    → list_orders    (any user, 200)
```

**ValueError → HTTP status mapping (same pattern as Phase 4):**

```python
except ValueError as e:
    if "not found" in str(e).lower():
        raise HTTPException(404, ...)
    if "insufficient stock" in str(e).lower():
        raise HTTPException(409, ...)
    if "cannot be cancelled" in str(e).lower():
        raise HTTPException(409, ...)
    raise HTTPException(400, ...)
```

### Why 201 for create, 200 for cancel

- `POST /orders` creates a new top-level resource → `201 Created`
- `PATCH /orders/{id}/cancel` performs an action on an existing resource → `200 OK`

---

## Step 5 — Wire into main.py + Migrate

### `backend/app/main.py` — what changed

```python
from app.routers.orders import router as orders_router
app.include_router(orders_router)   # added
```

### Migration `8e706f6828f0`

This migration does four things:

```sql
-- 1. Create orders table
CREATE TABLE orders (
    id            VARCHAR(36) PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    status        ENUM('PENDING','FULFILLED','CANCELLED') NOT NULL,
    created_by    VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 2. Create order_items table
CREATE TABLE order_items (
    id           VARCHAR(36) PRIMARY KEY,
    order_id     VARCHAR(36) REFERENCES orders(id) ON DELETE CASCADE,
    product_id   VARCHAR(36) REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,   -- snapshot
    product_sku  VARCHAR(100) NOT NULL,   -- snapshot
    quantity     INTEGER NOT NULL,
    unit_price   NUMERIC(10,2) NOT NULL,  -- snapshot
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 3. Add product_sku to stock_movements (new snapshot column)
ALTER TABLE stock_movements ADD COLUMN product_sku VARCHAR(100);

-- 4. Backfill product_sku from products table
UPDATE stock_movements sm
SET product_sku = p.sku
FROM products p
WHERE sm.product_id = p.id;

-- 5. Make product_sku NOT NULL and product_id nullable
ALTER TABLE stock_movements ALTER COLUMN product_sku SET NOT NULL;
ALTER TABLE stock_movements ALTER COLUMN product_id DROP NOT NULL;
```

### Why the stock_movements table was also changed

- `product_sku` added as a snapshot — if a product is deleted, the movement record still shows what SKU it was for
- `product_id` made nullable — if a product is hard-deleted, existing movement records survive with `product_id = NULL`, but `product_sku` still holds the identity

---

## Step 6 — Stock Service Update
### `backend/app/services/stock_service.py` — what changed

Three additions to `adjust_stock`:

```python
async def adjust_stock(
    self,
    product_id: str,
    data: StockAdjustRequest,
    adjusted_by: str,
    adjusted_by_name: str = "",   # NEW — for structured logging
    commit: bool = True,          # NEW — False = flush only, caller owns transaction
) -> StockMovement:

    # ... existing logic unchanged ...

    movement = StockMovement(
        product_id=product_id,
        product_sku=product.sku,   # NEW — snapshot survives product deletion
        ...
    )

    if commit:
        await self.db.commit()
        await self.db.refresh(movement)
    else:
        await self.db.flush()      # staged, not committed
```

### Why `commit=False` is the right design

```
BEFORE (broken — premature commits):
  adjust_stock() → commit()   ← order half-saved
  adjust_stock() → commit()   ← still half-saved
  create_order final commit() ← too late, already fragmented

AFTER (correct — one transaction):
  adjust_stock(commit=False) → flush()   ← staged
  adjust_stock(commit=False) → flush()   ← staged
  create_order db.commit()               ← ONE commit, all or nothing ✅
```

---

## Step 7 — Tests
### `backend/tests/test_orders.py` — 25 tests

| Test | What it proves |
|---|---|
| `test_user_can_create_order` | 201, correct shape, all snapshot fields present |
| `test_create_order_reduces_stock` | Stock decreases by exact ordered quantity |
| `test_create_order_multiple_items` | Both products updated correctly |
| `test_create_order_generates_ship_movements` | SHIP movement in audit trail |
| `test_create_order_insufficient_stock_returns_409` | Cannot over-order |
| `test_create_order_product_not_found_returns_404` | Bad product_id rejected |
| `test_create_order_empty_items_returns_422` | Schema rejects empty list |
| `test_create_order_zero_quantity_returns_422` | Schema rejects zero quantity |
| `test_create_order_duplicate_product_returns_422` | model_validator catches duplicates |
| `test_create_order_inactive_product_returns_404` | Soft-deleted products not orderable |
| `test_create_order_partial_failure_rolls_back` | **Atomicity — most important test** |
| `test_create_order_requires_auth` | 401 without token |
| `test_admin_can_cancel_order` | 200, status becomes CANCELLED |
| `test_cancel_order_restores_stock` | Stock fully restored after cancellation |
| `test_cancel_order_generates_receive_movements` | RECEIVE movement in audit trail |
| `test_cancel_already_cancelled_order_returns_409` | Cannot cancel twice |
| `test_cancel_non_existent_order_returns_404` | Bad order_id rejected |
| `test_regular_user_cannot_cancel_order` | 403 for non-admin |
| `test_cancel_order_requires_auth` | 401 without token |
| `test_get_order_by_id` | Correct data returned |
| `test_get_non_existent_order_returns_404` | Bad ID rejected |
| `test_get_order_requires_auth` | 401 without token |
| `test_list_orders_returns_all` | Correct total and count |
| `test_list_orders_pagination` | Correct page maths |
| `test_list_orders_requires_auth` | 401 without token |

---

## Bugs Fixed Along the Way

| Bug | Why it happened | How it was fixed |
|---|---|---|
| `400` on order creation | `StockService.adjust_stock` was called with `adjusted_by_name` keyword arg that didn't exist in the signature yet | Added `adjusted_by_name: str = ""` parameter to `adjust_stock` |
| `ValidationError for OrderResponse` | After `db.commit()`, SQLAlchemy expires all attributes. `order.items` relationship was never loaded, Pydantic crashed building the response | Re-fetch the order after commit using `SELECT ... selectinload(Order.items)` in both `create_order` and `cancel_order` |
| `OrderStatus` case mismatch | `OrderStatus` enum values were lowercase (`"pending"`) but tests expected uppercase (`"PENDING"`) | Changed enum values to uppercase — consistent with `MovementType` |
| `404` on `/stock/{id}/history` after order creation | `StockService.adjust_stock` called `db.commit()` inside the order transaction. Each premature commit fragmented the transaction and left the SQLite in-memory test DB in an inconsistent state | Added `commit: bool = True` flag to `adjust_stock`. `OrderService` calls with `commit=False`, then does one final `db.commit()` |
| `ValidationError: created_by_name Field required` | `StockMovementResponse` had a `created_by_name` field that never existed on the `StockMovement` model | Removed `created_by_name` from `StockMovementResponse` entirely |

---

## Security Habits Established This Phase

1. **Any user can place orders, only admin can cancel** — cancellation is a destructive stock operation. Admin-only, same rule as all writes.
2. **Pre-flight validation before any writes** — we never create a partial order. All checks pass first, then we write everything atomically.
3. **Price snapshots are immutable** — `unit_price` is copied at order time. The client never sends a price — the server reads it from the product. Price manipulation is impossible.
4. **Atomic transactions across services** — `OrderService` uses `commit=False` so stock adjustments, order items, and the order itself all commit in one transaction. No half-saved state is ever possible.
5. **Cancelled orders restore stock via RECEIVE movements** — restoring stock is not a direct `product.quantity += n`. It goes through `StockService.adjust_stock`, which creates a traceable `RECEIVE` movement in the audit log.
6. **Hard-deleted products don't break order cancellation** — we check `item.product_id is None` before calling stock restore. We log a warning and skip, rather than crashing.

---

## What's Next — Phase 6

Phase 5 completes the core inventory flow. Phase 6 will add a **RabbitMQ consumer** — a background worker that reads the `low_stock_alerts` queue that Phase 4 already publishes to, and acts on it. This separates the alert producer (the API) from the alert consumer (the worker), demonstrating true async messaging architecture.
