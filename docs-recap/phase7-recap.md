# Phase 7 Recap — Redis Caching, Invalidation, Test Fixes, and Read Performance

## What Is Covered

This phase was about adding **Redis caching** to the Inventory Manager in a way that fits real backend rules, not just “save something in Redis and hope.” The work had three connected parts:

1. build reusable cache helpers in the Redis utility layer;
2. cache the expensive read endpoints with the right TTLs;
3. invalidate stale cache correctly on writes and prove it with tests.

Think of the phase like this:

```text
PART 1
Teach the project how to read/write cache safely

PART 2
Use cache for product list and stock history

PART 3
Bust stale cache after writes and verify it with tests
```

That means this phase was not only about speed. It was really about **correctness, invalidation strategy, helper design, mocking discipline, and test stability**.

---

## Big Picture

Before this phase, every request for the product list or stock movement history always went straight to the database.

```text
Before
request -> service -> database every time -> return
```

After this phase, those read paths now use a cache-aside flow.

```text
After
request -> service -> Redis check
                    ├─ hit  -> return cached result
                    └─ miss -> query DB -> store in Redis -> return
```

That matters because product listing and stock history are classic read-heavy endpoints. They are asked often, their response shape is predictable, and they do not need a fresh database hit every single time.

At the same time, the phase also handled the part that usually separates toy caching from real caching:

```text
writes must invalidate stale reads
```

Without that, the cache would make the app faster but wrong.

---

## Part 1 — Reusable Cache Helpers in `redis_client.py`

The first step was expanding the Redis utility layer. Before Phase 7, Redis was already used for refresh tokens. This phase added a second responsibility: generic caching helpers for service-layer reads.

### New helper layer

The new helper set looked like this:

```text
cache_get(key)
cache_set(key, value, ttl)
cache_delete(key)
cache_delete_pattern(pattern)
```

Mental model:

```text
service wants cached data
      │
      ▼
redis_client helper
      │
      ├─ serialise/deserialise JSON
      ├─ talk to Redis
      └─ keep service code clean
```

### Why this was the right design

This follows the project rule that **services own business logic** while utility modules handle infrastructure details. The service should decide *when* to cache and *what* key to use, but it should not be full of raw Redis JSON plumbing.

### JSON serialisation choice

Redis stores strings, so the cache helpers convert Python data to JSON on write and parse it back on read.

```text
Python dict/list
   ↓ json.dumps
Redis string
   ↓ json.loads
Python dict/list
```

That keeps the service code simple and makes the cache helpers reusable across multiple response shapes.

---

## The `SCAN` Lesson — Why Pattern Delete Needed Care

One of the most important details in this phase was cache invalidation by pattern.

A first instinct might be:

```text
KEYS products:list:*
```

But that is dangerous in production because `KEYS` scans the full keyspace in a blocking way.

### Correct approach used

The phase used Redis `SCAN` instead.

```text
cursor = 0
loop
  scan a chunk
  delete found keys
  continue until cursor returns to 0
```

Mental model:

```text
KEYS = stop the shop and search every shelf now
SCAN = walk shelf by shelf without blocking the shop
```

That makes `cache_delete_pattern()` the safe foundation for invalidating paginated cache keys like:

```text
products:list:1:10
products:list:2:10
stock:history:prd_xxx:1:10
stock:history:prd_xxx:2:10
```

---

## Part 2 — Product List Caching

The first actual cached read was the product list endpoint.

### Why products list was a good cache target

The project roadmap already identified product list as one of the expensive reads worth caching. That makes sense because:

- it is paginated;
- it is read often;
- it changes less frequently than stock history;
- it has a stable response shape.

### Cache key design

The product list key used both page and page size:

```text
products:list:{page}:{page_size}
```

That is important because these are different cached results:

```text
/products?page=1&page_size=10
/products?page=1&page_size=25
```

If `page_size` were missing from the key, one request could overwrite the other and return the wrong payload shape.

### Product TTL choice

Products were given the longer TTL:

```text
300 seconds = 5 minutes
```

That is a sensible tradeoff because products do change, but not nearly as often as stock movement history.

---

## Product Write Invalidation

Caching reads is only half the story. The real reliability work in this phase was invalidating product list cache after writes.

### Which writes invalidate product list cache

```text
create product
update product
delete product
```

All three can change what appears in the list, so all three must bust the cached list pages.

### Pattern used

```text
products:list:*
```

Mental model:

```text
A new or changed product can affect many pages
so do not guess one exact key
delete all cached product-list pages
```

This is the correct tradeoff for this project. It is simple, safe, and consistent.

---

## Part 3 — Stock History Caching

The second cached read was stock movement history.

### Why stock history is a separate case

Stock history also fits caching well because it is paginated and often viewed repeatedly. But it changes more often than the product list, so it cannot have the same freshness rules.

That is why this phase used a shorter TTL here.

```text
60 seconds = 1 minute
```

### Stock history key design

The safe key shape used:

```text
stock:history:{product_id}:{page}:{page_size}
```

That is slightly stricter than the simplified roadmap note, and it is the correct real implementation because page size changes the returned dataset.

### Why the shorter TTL matters

Stock movement history is closer to an event feed than a catalogue. It changes whenever stock is adjusted, so it should expire more quickly even before explicit invalidation.

---

## Stock Write Invalidation

The stock side of this phase had one extra subtlety: invalidation must happen only after a real committed write.

### Why commit timing mattered

`StockService.adjust_stock()` already supported:

```python
commit: bool = True
```

That means the service can either commit immediately or be part of a bigger outer transaction.

### Correct rule used

```text
if commit=True
    commit DB
    invalidate stock history cache
else
    flush only
    do not invalidate yet
```

Why this is correct:

```text
invalidate too early
    ↓
cache disappears for a change that might still roll back
```

That would break the project rule of **one transaction per operation**.

### Pattern used

```text
stock:history:{product_id}:*
```

This removes all cached history pages for that product after a successful stock change.

---

## The Cache-Aside Pattern in Practice

This phase is a clean example of the cache-aside pattern.

### Read flow

```text
1. Build cache key
2. cache_get(key)
3. If hit -> rebuild response model and return
4. If miss -> query DB
5. Build response model
6. cache_set(key, response, ttl)
7. Return response
```

### Why this pattern is good

It keeps PostgreSQL as the source of truth while Redis acts as a short-lived speed layer.

Analogy:

```text
PostgreSQL = warehouse
Redis      = front desk tray with the most requested papers
```

The tray is faster, but the warehouse is still the truth.

---

## Test Work Done in This Phase

A major part of the phase was proving the caching logic with tests instead of just trusting the code.

### New product cache tests

The product side added tests for:

1. cache hit returns cached list;
2. cache miss stores fresh list;
3. create invalidates product list cache;
4. update invalidates product list cache;
5. delete invalidates product list cache.

### New stock cache tests

The stock side added tests for:

1. movement history cache hit returns cached response;
2. movement history cache miss stores fresh response;
3. stock adjustment invalidates history cache;
4. cached history still works for a regular read user.

Mental model:

```text
Products -> 5 new cache tests
Stock    -> 4 new cache tests
```

That is exactly the right split because products had three different write invalidation paths while stock had one main invalidation path.

---

## The Test Fixture Bug That Appeared

One real bug during the phase came from the Redis mock setup in `conftest.py`.

### The failure

After adding cache helpers, many tests failed with an error like:

```text
TypeError: object MagicMock can't be used in 'await' expression
```

### Why it happened

The existing fixture was patching a Redis object in a way that left some awaited methods as plain `MagicMock` instead of `AsyncMock`.

That became a problem as soon as the new cache layer started awaiting methods like:

```text
get
setex
delete
scan
```

### The correct fix

Instead of relying on a generic patched object, the phase switched to an explicit async Redis fake where every awaited method is an `AsyncMock`.

```text
mock_redis.get     = AsyncMock(...)
mock_redis.setex   = AsyncMock(...)
mock_redis.delete  = AsyncMock(...)
mock_redis.scan    = AsyncMock(...)
mock_redis.aclose  = AsyncMock(...)
```

This is an important testing lesson:

```text
if the real code does await something,
that test double must also be awaitable
```

---

## The Patching Lesson — Patch Where the Symbol Is Used

Another good testing lesson in this phase was patch target accuracy.

The cache tests needed to patch symbols like:

```text
app.services.product_service.cache_get
app.services.product_service.cache_set
app.services.product_service.cache_delete_pattern

app.services.stock_service.cache_get
app.services.stock_service.cache_set
app.services.stock_service.cache_delete_pattern
```

not the original utility module path.

### Why this matters

When a service does:

```python
from app.utils.redis_client import cache_get
```

Python binds that name inside the service module. So the test must patch the service module’s local name, not the original source module.

This is the same kind of bug pattern already seen earlier in the project with logger patching.

---

## Updated Test Count

Before this phase, the backend test total was:

```text
70 tests
```

After the new cache tests:

```text
79 tests
```

Breakdown:

```text
test_auth.py      8
test_products.py  22
test_stock.py     21
test_orders.py    25
test_worker.py    3
```

The main point is not only the bigger number. It is that the new tests cover both:

- the happy cache path;
- the stale-cache invalidation path.

That is what makes Phase 7 believable in an interview.

---

## What You Built by the End of the Phase

By the end of the phase, the backend had a working Redis caching layer for its most obvious expensive reads.

### Final read/write picture

```text
GET /products
  -> Redis cache-aside with 300s TTL

POST/PUT/DELETE /products
  -> invalidate products:list:*

GET /stock/{product_id}/history
  -> Redis cache-aside with 60s TTL

POST /stock/{product_id}/adjust
  -> invalidate stock:history:{product_id}:*
```

### In practical terms

Before this work:

```text
all read traffic hit PostgreSQL
```

After this work:

```text
repeated list/history reads can be served from Redis
writes clear stale cache correctly
```

That is a meaningful backend improvement.

---

## What This Phase Taught Technically

### 1. Caching is a correctness problem, not just a speed trick

Fast but stale data is still wrong data. Invalidating after writes is as important as caching reads.

### 2. Key design matters

If the cache key ignores pagination inputs like `page_size`, the app can return the wrong response.

### 3. TTL should match data volatility

Products can live longer in cache. Stock history needs a shorter life.

### 4. `SCAN` is safer than `KEYS`

Pattern invalidation should not block Redis.

### 5. Transaction timing matters for invalidation

Bust cache after a successful commit, not before.

### 6. Async tests must use async doubles

If the code awaits a dependency, a plain `MagicMock` will break.

### 7. Patch where used, not where defined

That is one of the most common and most useful Python testing lessons.

---

## Why This Phase Was Valuable

This phase was valuable because it moved the project from “good CRUD backend” toward “backend with real production-style thinking.”

It was not just:

```text
store something in Redis
```

It was:

```text
design helpers
choose keys
pick TTLs
handle serialisation
invalidate on writes
respect transactions
fix async mocks
prove it with tests
```

That is much closer to real backend engineering.

---

## Final State After This Phase

By the end of the phase, you had:

- reusable Redis cache helpers added to `redis_client.py`;
- product list caching with 5-minute TTL;
- stock history caching with 1-minute TTL;
- product cache invalidation on create, update, and delete;
- stock history invalidation after committed stock adjustment;
- fixed async Redis mocking in the shared test fixture;
- new cache tests for both products and stock;
- a total backend test count of 79 passing tests.

---

## Recap in One Diagram

```text
PHASE RECAP

A. Redis utility upgrade
   refresh-token-only Redis usage
      ↓
   reusable cache helpers added

B. Product caching
   GET /products
      ↓
   Redis cache-aside (300s)
      ↓
   writes invalidate products:list:*

C. Stock caching
   GET /stock/{id}/history
      ↓
   Redis cache-aside (60s)
      ↓
   stock adjust invalidates stock:history:{id}:*

D. Test stability
   broken async Redis mock
      ↓
   proper AsyncMock-based fixture
      ↓
   cache tests pass
```

---

## What This Means for the Project

After this phase, the Inventory Manager is no longer only a CRUD + queue backend. It now includes a realistic caching layer with explicit invalidation strategy.

That is a strong portfolio upgrade because it shows:

- Redis beyond auth token storage;
- cache-aside architecture;
- invalidation discipline;
- awareness of stale-data risks;
- safe Redis scanning patterns;
- async testing and mocking maturity.
