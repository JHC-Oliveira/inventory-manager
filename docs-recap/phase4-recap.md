# Phase 4 Recap — Stock Management

## What This Phase Is About

Phase 3 left us with products sitting in the database with a `quantity` number. That number tells you the current state — but nothing else. How did it get to 15? Was it 100 last week? Who changed it? Did we receive stock, ship an order, or did someone make a manual correction?

Phase 4 answers all of those questions. Every single stock change now creates a permanent `StockMovement` record — an append-only audit log that can never be edited, only read. On top of that, when stock drops to or below the alert threshold, the system automatically publishes a message to RabbitMQ so that any consumer (email, Slack, reorder system) can react independently.

By the end of Phase 4 you can:
- Receive stock into the system
- Ship stock out of the system
- Make manual corrections (damage, recount)
- View the full paginated history of every change per product
- Have the system automatically alert RabbitMQ when stock is critically low

---

## The Big Picture — How a Stock Adjustment Flows

Before touching any code, it helps to see the full journey of a request from the client all the way to the database and RabbitMQ.

```
Client
  │
  │  POST /stock/{product_id}/adjust
  │  Authorization: Bearer <admin_token>
  │  Body: { movement_type, quantity_change, note }
  ▼
Router  (app/routers/stock.py)
  │
  │  1. get_current_admin     → verify JWT, confirm is_admin=True
  │  2. StockAdjustRequest    → validate body shape and business rules
  │  3. Call StockService.adjust_stock()
  ▼
Service  (app/services/stock_service.py)
  │
  │  4. Load product from DB           → 404 if not found or inactive
  │  5. Calculate quantity_before and quantity_after
  │  6. Reject if quantity_after < 0   → ValueError "insufficient stock"
  │  7. Create StockMovement record    → append to audit log
  │  8. Update product.quantity        → reflect new stock level
  │  9. Commit both atomically         → both succeed or both fail, never half-saved
  │  10. Is product.is_low_stock?      → publish alert to RabbitMQ
  ▼
Response  200 OK
  {
    id, product_id, movement_type,
    quantity_change, quantity_before, quantity_after,
    note, created_by, created_at
  }

              ┌─────────────────────────────────────┐
              │           RabbitMQ                  │
              │   exchange: inventory               │
              │   queue:    low_stock_alerts        │
              │   message: {                        │
              │     product_id, sku,                │
              │     current_quantity, threshold     │
              │   }                                 │
              └─────────────────────────────────────┘
                        ▲
                        │ published AFTER DB commit
                        │ so no ghost alerts if commit fails
```

**Key insight:** The movement record and the quantity update always happen in the same database commit. Either both are saved, or neither is. You can never end up in a state where stock changed but there is no record of it, or a record exists but the stock did not change.

---

## Step 1 — RabbitMQ Config & Utility

### Files touched
- `app/config.py` — added `rabbitmq_url`
- `app/utils/rabbitmq.py` — created

### What we built

RabbitMQ needs to be connected when the server starts, not on every individual request. We added the URL to config and built three functions:

```python
# app/config.py — new field
rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
```

```python
# app/utils/rabbitmq.py

_connection = None   # module-level — created once, shared by all requests
_channel    = None

async def connect_rabbitmq():
    """Called on startup. Establishes the connection once."""

async def close_rabbitmq():
    """Called on shutdown. Gracefully closes the connection."""

async def publish_low_stock_alert(product_id, sku, current_quantity, threshold):
    """Called by the service when stock drops to or below threshold."""
```

### Why the decisions were made this way

**Module-level `_connection` and `_channel`:**
Creating a new RabbitMQ connection on every single HTTP request would be like hanging up the phone and calling again for every sentence. Extremely slow and wasteful. The connection is created once at startup and every request reuses it — exactly the same pattern as the database engine.

**`connect_rabbitmq()` in `lifespan`, not in the function itself:**
If the publish function created the connection lazily on first use, the first request to trigger a low-stock alert would pay the connection cost. Doing it in `lifespan` means the connection is ready before any request arrives.

**Publish AFTER the DB commit, never before:**
```
WRONG — publish before commit:
  RabbitMQ receives alert   ✅
  DB commit fails           ❌
  Consumer reacts to alert but stock change never happened → ghost alert ❌

CORRECT — publish after commit:
  DB commit succeeds        ✅
  Publish alert             ✅
  Both in sync              ✅
```
The database is the source of truth. Notify the outside world only once the truth has been written.

---

## Step 2 — StockMovement Model

### File created
- `app/models/stock_movement.py`

### What we built

```python
class MovementType(PyEnum):
    RECEIVE = "RECEIVE"   # stock arriving — supplier delivery, purchase order
    SHIP    = "SHIP"      # stock leaving  — customer order fulfilled
    ADJUST  = "ADJUST"    # manual correction — damage, recount, write-off

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id               # UUID primary key — auto-generated
    product_id       # FK → products.id   ondelete CASCADE
    movement_type    # RECEIVE | SHIP | ADJUST
    quantity_change  # signed integer — +50 or -30
    quantity_before  # stock level BEFORE this movement
    quantity_after   # stock level AFTER this movement
    note             # optional free text — "Order #1001", "3 units damaged"
    created_by       # FK → users.id   ondelete SET NULL
    created_at       # timestamp — set once, never updated
```

### Why the decisions were made this way

**`MovementType` as a Python Enum, not a plain string:**
Using a plain string would accept any value — `"recieve"`, `"RECIVE"`, `"misc"` — with no validation. The Enum means only `RECEIVE`, `SHIP`, or `ADJUST` are accepted anywhere in the codebase. Pydantic validates it at the API boundary, SQLAlchemy stores it in the DB, and Python autocompletes it in the editor.

**`ondelete="CASCADE"` on `product_id`:**
Stock movements are children of a product. They are meaningless without it. If a product is hard-deleted, its movements should be deleted too — they refer to something that no longer exists.

Compare this to `created_by` which uses `ondelete="SET NULL"` — if the admin who made the adjustment is deleted, the movement record should survive with `created_by=None`. The movement happened; it just no longer knows who did it.

**Three quantity fields — `before`, `change`, `after`:**
You could derive `quantity_after = quantity_before + quantity_change`, so why store all three? Two reasons:

1. **Audit integrity** — if you need to know "what was the stock at 3pm on Tuesday?", one row gives you the exact answer with no calculation.
2. **Forensics** — if `quantity_before + quantity_change ≠ quantity_after`, something went wrong and you can detect it immediately.

**`quantity_change` is signed:**
```
RECEIVE  +50  → stock goes up
SHIP     -30  → stock goes down
ADJUST   -5   → correction downward (damage)
ADJUST   +3   → correction upward (recount found extra units)
```
One field handles every direction. The sign tells you everything.

**No `updated_at` column:**
Stock movement records are immutable — append only. Once created, they are never changed. Having an `updated_at` column would suggest rows can be edited, which would be misleading and wrong.

---

## Step 3 — StockMovement Schemas

### File created
- `app/schemas/stock_movement.py`

### What we built

```python
class StockAdjustRequest(BaseModel):
    """What the client sends to POST /stock/{product_id}/adjust"""
    movement_type:   MovementType
    quantity_change: int
    note:            str | None = None

class StockMovementResponse(BaseModel):
    """Shape of one movement record returned to the client"""
    id, product_id, movement_type
    quantity_change, quantity_before, quantity_after
    note, created_by, created_at

class StockMovementListResponse(BaseModel):
    """Paginated movement history"""
    items:       list[StockMovementResponse]
    total:       int
    page:        int
    page_size:   int
    total_pages: int
```

### Why the decisions were made this way

**`@field_validator` — rejects zero:**
```python
@field_validator("quantity_change")
def quantity_change_not_zero(cls, v):
    if v == 0:
        raise ValueError("quantity_change cannot be zero")
    return v
```
A movement of zero changes nothing and records nothing useful. It pollutes the audit log with meaningless entries. Reject it at the schema level before it even reaches the service.

**`@model_validator` — enforces sign rules across two fields together:**
A `@field_validator` can only see one field at a time. Some rules need to see two fields together. This is what `@model_validator(mode="after")` is for:

```python
RECEIVE + quantity_change=-10  → invalid ❌  you can't receive negative stock
SHIP    + quantity_change=+10  → invalid ❌  shipping adds stock? makes no sense
ADJUST  + quantity_change=-5   → valid   ✅  correction downward
ADJUST  + quantity_change=+3   → valid   ✅  correction upward
```

**Why isn't the "below zero" check here?**
The schema doesn't know the current stock level — it only sees what the client sent. Checking `quantity_after < 0` requires reading the database, so that check lives in the service where the DB is available.

**Client never sends `quantity_before` or `quantity_after`:**
```
Client sends:    { movement_type, quantity_change, note }
Server derives:  quantity_before = product.quantity  (read from DB at this exact moment)
                 quantity_after  = quantity_before + quantity_change
```
If the client could send `quantity_before`, they could lie about what the stock was. The server reads it from the DB at the moment of the transaction — this is the only value that can be trusted.

---

## Step 4 — Stock Service

### File created
- `app/services/stock_service.py`

### What we built

```python
class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def adjust_stock(product_id, data, adjusted_by) -> StockMovement
    async def get_movement_history(product_id, page, page_size) -> StockMovementListResponse
```

### The `adjust_stock` flow — step by step

```python
# 1. Load the product
product = await self.db.execute(select(Product).where(...))
if product is None:
    raise ValueError("Product not found")        # → router translates to 404

# 2. Calculate quantities
quantity_before = product.quantity
quantity_after  = quantity_before + data.quantity_change

# 3. Prevent going below zero
if quantity_after < 0:
    raise ValueError("Insufficient stock")       # → router translates to 409

# 4. Create movement record — BEFORE updating the product
movement = StockMovement(
    quantity_before=quantity_before,
    quantity_after=quantity_after,
    ...
)
self.db.add(movement)

# 5. Update the product
product.quantity = quantity_after

# 6. Commit BOTH atomically
await self.db.commit()

# 7. Publish alert AFTER commit
if product.is_low_stock:
    await publish_low_stock_alert(...)
```

### Why the decisions were made this way

**Steps 4 and 5 — movement created before product update, both in same commit:**
Both changes are staged in SQLAlchemy's unit of work before any commit happens. When `commit()` is called, they go to the database together as a single atomic transaction:
```
commit succeeds → movement saved AND product.quantity updated  ✅
commit fails    → neither saved, database unchanged            ✅
movement saved but product not updated                         ❌ can never happen
```

**Step 3 — insufficient stock check is in the service, not the schema:**
The schema validated that `SHIP` has a negative `quantity_change`. But the schema doesn't know if you actually have that many units. The service reads `product.quantity` from the DB and can do the real check:
```
product.quantity = 5
quantity_change  = -10
quantity_after   = -5  → rejected ❌ you cannot ship 10 when you only have 5
```

**`total_pages` guard for empty results:**
```python
total_pages = math.ceil(total / page_size) if total > 0 else 1
```
Without the guard: `math.ceil(0 / 10) = 0`, meaning zero pages exist. But the client is on page 1 — returning `page=1, total_pages=0` is contradictory. When there are no results, return `total_pages=1`. The client is on the only (empty) page.

**History is newest first:**
```python
.order_by(StockMovement.created_at.desc())
```
When checking stock history, you always care about what happened recently. The most recent event belongs at the top.

---

## Step 5 — Stock Router

### File created
- `app/routers/stock.py`

### What we built

```python
# Admin only — stock changes require elevated permission
POST /stock/{product_id}/adjust
    → Depends(get_current_admin)
    → 200 StockMovementResponse

# Any logged-in user — read-only, no permission risk
GET /stock/{product_id}/history
    → Depends(get_current_user)
    → 200 StockMovementListResponse
```

### Why the decisions were made this way

**Two different auth levels on the same router:**
Adjusting stock changes data permanently — admin only. Reading history is read-only, it changes nothing — any authenticated user can do it. The same rule established in Phase 3: writes are admin, reads are any user.

**`200 OK` on adjust, not `201 Created`:**
```
201 Created  → you created a new top-level resource (POST /products)
200 OK       → you performed an action with a side effect (POST /stock/.../adjust)
```
A stock adjustment is an action performed on existing data. The movement record is a side effect of that action, not the primary resource being created.

**ValueError to HTTP status translation — one error, three possible codes:**
```python
except ValueError as e:
    if "not found" in str(e).lower():
        raise HTTPException(404)
    if "insufficient stock" in str(e).lower():
        raise HTTPException(409)
    raise HTTPException(400)
```
The service raises plain `ValueError` — it speaks Python, not HTTP. The router is the HTTP translator. It reads the message and decides which status code fits the situation. This keeps the service reusable in any context (tests, scripts, background jobs) without being tied to HTTP.

**`product_id` from the URL, never from the body:**
```
POST /stock/abc-123-def/adjust
                ↑
    FastAPI extracts this automatically from {product_id} in the route definition
```
The client never sends `product_id` in the request body. It is part of the URL — this is RESTful design. You are operating on a specific resource identified by its ID in the path.

---

## Step 6 — Wire into `main.py` + Migrate

### File updated
- `app/main.py`

### What changed — three additions only

```python
# New imports
from app.utils.rabbitmq import connect_rabbitmq, close_rabbitmq
from app.routers.stock import router as stock_router

# Lifespan — startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    await connect_rabbitmq()       # ← new: connect on startup
    yield
    await close_rabbitmq()         # ← new: disconnect on shutdown
    await close_redis()

# Router registration
app.include_router(stock_router)   # ← new: expose the endpoints
```

Without `include_router`, the stock router exists as a Python file but FastAPI has no idea it exists. Every request to `/stock/...` would return `404 Not Found`.

### Migration

```bash
docker compose exec api alembic revision --autogenerate -m "add stock_movements table"
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

Alembic detects `StockMovement` (registered in `models/__init__.py`), generates the migration, and creates the `stock_movements` table in PostgreSQL.

---

## Step 7 — Tests

### File created
- `tests/test_stock.py`

### conftest.py update — adding the RabbitMQ mock

The existing `conftest.py` only mocked Redis. When stock tests triggered a low-stock alert, `publish_low_stock_alert()` tried to use a real RabbitMQ connection that doesn't exist in the test environment.

The fix was to nest a third mock inside the existing two:

```python
# conftest.py — client fixture
with patch("app.utils.redis_client.redis_client") as mock_redis:
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock(return_value=True)

    with patch("app.utils.redis_client.get_redis", AsyncMock(return_value=mock_redis)):
        with patch(
            "app.utils.rabbitmq.publish_low_stock_alert",   # ← new
            new=AsyncMock(return_value=None),
        ):
            async with AsyncClient(...) as ac:
                yield ac                                     # ← one single yield
```

**Why only mock `publish_low_stock_alert` and not `connect_rabbitmq`?**
```
connect_rabbitmq() → runs inside lifespan (startup)
                   → lifespan does NOT run in tests    ✅ not a problem

publish_low_stock_alert() → called inside the service
                          → called during tests        ❌ needs mocking
```

**The Russian doll rule — one yield, all mocks active at once:**
Think of each `with patch(...)` block as a layer wrapping the next. The `yield` must sit at the centre so all three mocks are active at the same time when the test runs. A second `yield` outside the blocks would break the fixture — pytest would stop at the first `yield` and never activate the outer mocks.

```
Redis mock
  └── get_redis mock
        └── RabbitMQ mock
              └── yield   ← all three active here
```

### The 17 tests and what each one proves

| Test | What it proves |
|---|---|
| `test_receive_stock` | RECEIVE increases quantity, movement record has correct before/after/change |
| `test_ship_stock` | SHIP decreases quantity, movement record is correct |
| `test_adjust_stock_upward` | ADJUST with positive change increases quantity |
| `test_adjust_stock_downward` | ADJUST with negative change decreases quantity |
| `test_ship_more_than_available_returns_409` | Cannot ship more units than in stock |
| `test_receive_with_negative_quantity_returns_422` | RECEIVE must always be positive — schema rule |
| `test_ship_with_positive_quantity_returns_422` | SHIP must always be negative — schema rule |
| `test_quantity_change_zero_returns_422` | Zero change is meaningless — schema rule |
| `test_adjust_stock_product_not_found_returns_404` | Non-existent product_id returns 404 |
| `test_adjust_stock_requires_admin` | Regular user gets 403 — cannot adjust stock |
| `test_adjust_stock_requires_auth` | No token gets 401 |
| `test_movement_history_returns_movements` | History returns correct count, newest movement first |
| `test_movement_history_empty_product` | No movements yet — empty list, `total_pages=1` |
| `test_movement_history_pagination` | 5 movements, page_size=2 → 3 pages, 2 items on page 1 |
| `test_movement_history_regular_user_can_view` | Read-only history is accessible to regular users |
| `test_movement_history_requires_auth` | No token gets 401 |
| `test_movement_history_product_not_found` | Non-existent product_id returns 404 |

---

## Bugs Fixed Along the Way

| Bug | What happened | Why it happened | How it was fixed |
|---|---|---|---|
| `KeyError: 'access_token'` on all stock tests | Login was failing inside the test helper functions | `test_stock.py` defined its own `get_admin_token()` helper that registered users without `full_name` — the register endpoint rejected the request with 422, so login also failed | Deleted the local helpers entirely and used the `admin_token` and `user_token` fixtures from `conftest.py` directly — same pattern as `test_products.py` |
| RabbitMQ errors in tests | `publish_low_stock_alert()` tried to use a real RabbitMQ connection during tests | `conftest.py` only mocked Redis — RabbitMQ was never mocked | Added `patch("app.utils.rabbitmq.publish_low_stock_alert")` nested inside the existing Redis mocks |
| Double `yield` broke the `client` fixture | Adding the RabbitMQ mock outside the Redis block created a second `yield` | The RabbitMQ patch was placed after the Redis `with` block ended, outside the nesting | Moved all three mocks into a nested structure with a single `yield` at the centre |

---

## Security Habits Established This Phase

1. **Stock adjustments are admin-only** — `get_current_admin` dependency on the adjust endpoint. Regular users can read history but cannot change stock.
2. **Audit trail is immutable** — `StockMovement` records have no `updated_at`, are never edited, and cascade-delete only if the parent product is hard-deleted.
3. **Atomic commits** — the movement record and the product quantity update are always committed together. The database is never left in a half-updated state.
4. **Server owns `quantity_before`** — the client never sends this value. The server reads it from the database at the exact moment of the transaction.
5. **RabbitMQ publishes after commit** — the outside world is notified only after the database has confirmed the change. No ghost alerts from failed transactions.
6. **Service speaks Python, router speaks HTTP** — `ValueError` in the service, `HTTPException` in the router. The service remains testable and reusable outside of HTTP contexts.

---

## What's Next — Phase 5

Phase 5 builds Orders and Order Items. This is where Phase 4 pays off — creating an order will automatically call `StockService.adjust_stock()` with `SHIP` for every product in the order. Cancelling an order will call it again with `RECEIVE` to restore the stock. Every order-driven stock change will have a permanent movement record automatically, because we built the audit trail in Phase 4.

