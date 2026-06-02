# Phase 8 Recap — Reports & Analytics, Aggregate Queries, and Admin-Only Read Endpoints

## What Is Covered

This phase added the **reports and analytics** layer to the Inventory Manager. The work focused on turning raw product, order, and stock movement data into useful read-only summaries that are safe, fast, and easy to consume from the UI.

The phase had four connected parts:

1. build a dedicated reports service layer;
2. expose admin-only report endpoints;
3. use aggregate SQL queries for summaries and rankings;
4. prove the endpoints work with tests.

Think of this phase like this:

```text
PART 1
Collect data from existing models

PART 2
Shape it into report-friendly responses

PART 3
Expose it through admin-only routes

PART 4
Test every report path end to end
```

This phase was not about adding new business objects. It was about **making the existing data useful** without breaking the project rules around snapshots, async SQLAlchemy, and service-layer ownership.

---

## Big Picture

Before this phase, the backend already had products, stock movements, and orders, but there was no single place to answer questions like:

- What is the current inventory worth?
- Which products are low on stock?
- Which products are ordered the most?
- What is the movement history over time?

```text
Before
raw tables -> no analytics endpoints

After
raw tables -> report service -> admin-only report endpoints
```

That matters because dashboards and admin views usually need exactly this kind of data. They are read-heavy, derived from existing records, and best handled with aggregate queries instead of manual processing in the UI.

---

## Why Reports Matter

Reports are the “**manager view**” of the project.

```text
CRUD pages
  show one thing at a time

Reports
  show the whole system at a glance
```

That is useful because it gives the app a more complete product feel. A junior backend project feels much stronger when it can answer operational questions, not just create and update records.

This phase also reinforces a useful backend pattern: keep the HTTP layer thin, keep the business logic in services, and keep the response shapes in schemas.

---

## Part 1 — Report Schemas

The first step was defining report response schemas in `app/schemas/report.py`. These schemas act like contracts between the service and the client.

### Report shapes added

```text
StockSummaryItem
StockSummaryResponse

LowStockItem
LowStockResponse

TopProductItem
TopProductsResponse

MovementHistoryItem
MovementHistoryResponse
```

Mental model:

```text
database rows
   ↓
service logic
   ↓
report schema
   ↓
API response
```

### Why separate report schemas matter

Report responses are not the same as CRUD responses. They include derived values like:

- `inventory_value`
- `total_inventory_value`
- `total_quantity`
- `total_orders`
- `total_revenue`
- pagination metadata

That means the report layer should not reuse product/order schemas blindly. It needs purpose-built shapes.

### Movement history shape

Movement history uses the existing `created_by` field only.

```text
created_by: str | None
```

That matches the current project state and avoids inventing fields that do not exist in the schema.

---

## Part 2 — Report Service

The core of the phase was `ReportService` in `app/services/report_service.py`.

### Service responsibility

```text
router -> service -> database -> report response
```

The router only handles HTTP. The service owns the reporting logic. That fits the project rule that services must own business behavior.

### Stock summary

The stock summary report returns all active products with:

- current quantity,
- price,
- inventory value per product,
- low stock flag,
- low stock threshold,
- active status,
- total inventory value across all returned products.

```text
inventory_value = price x quantity
```

This is a classic aggregate report because it gives an overall view of stock value.

### Low stock report

The low stock report filters active products where:

```text
quantity <= low_stock_threshold
```

That lets the admin quickly see which items need attention.

### Top products report

The top products report groups order items by snapshot fields:

```text
product_sku
product_name
```

Then it calculates:

```text
sum(quantity)
count(order_item id)
sum(quantity * unit_price)
```

That means the report works from order snapshots, not live product data. That is important because history must remain valid even if a product later changes or is deleted.

### Movement history report

The movement history report returns stock movement rows with:

- product ID,
- product SKU snapshot,
- movement type,
- quantity before/after,
- quantity change,
- note,
- created_by,
- created_at.

It also supports:

- pagination,
- start date filter,
- end date filter.

This report uses `selectinload(StockMovement.creator)` so async SQLAlchemy does not attempt lazy loading later.

---

## Aggregate SQL Flow

The top-products report is the best example of the aggregate-query pattern.

```text
OrderItem rows
   ↓
GROUP BY product_sku, product_name
   ↓
SUM(quantity)
COUNT(id)
SUM(quantity * unit_price)
   ↓
TopProductsResponse
```

This is a strong Phase 8 skill because it shows you can use SQL for analytics instead of over-processing data in Python.

---

## Part 3 — Reports Router

The new router exposes the report endpoints under `/reports`.

```text
GET /reports/stock-summary
GET /reports/low-stock
GET /reports/top-products
GET /reports/movement-history
```

All of them are admin-only read endpoints.

### Why admin-only matters

Reports are operational and can expose business-sensitive information. That means the router uses `get_current_admin` to protect the endpoints.

```text
admin dependency
  -> permission gate
  -> route runs only for admins
```

That keeps the access model consistent with the rest of the project: admin writes, any user reads, except for privileged analytics.

---

## Part 4 — Testing

The biggest practical work in this phase was proving the new endpoints with API tests.

### What the tests cover

```text
- stock summary returns totals and items
- low stock returns only low-stock products
- top products aggregates order items correctly
- movement history returns ordered movement rows
- pagination works
- date filters work
- admin-only access is enforced
- unauthenticated access is rejected
```

### Why the tests mattered

Reports are easy to get “almost right” and still be wrong. Aggregates, filters, and pagination all need direct verification.

This phase also surfaced a useful bug: the order creation test helper needed to include `customer_name`, because the real `POST /orders` schema requires it. That is a good reminder that test data must match the live schema exactly.

---

## What Changed in the Project

After Phase 8, the backend gained:

- a dedicated report schema layer;
- a dedicated report service;
- admin-only analytics endpoints;
- aggregate query support for stock and orders;
- movement history reporting over the whole system;
- report tests that validate the new behavior.

```text
CRUD backend
   +
analytics layer
   =
more complete portfolio backend
```

That is a strong step toward a junior-dev-ready project because it shows you can build both transactional features and read-only operational views.

---

## Technical Lessons

### 1. Use snapshots for history

Top products and movement history rely on stored snapshots like product name, product SKU, and unit price. That keeps old records valid after product changes.

### 2. Use aggregate SQL for summaries

Reports are a good fit for `GROUP BY`, `COUNT`, and `SUM`.

### 3. Keep reports in services

The router should stay thin. The service should do the data shaping.

### 4. Protect analytics endpoints

Reports often reveal business-sensitive information, so admin-only access is a sensible rule.

### 5. Match tests to schemas exactly

When a schema changes, the test helper must change too.

---

## Final State After This Phase

By the end of Phase 8, the project had:

- four new report endpoints;
- a dedicated report schema file;
- a dedicated report service;
- admin-only protection on analytics routes;
- movement history with pagination and date filters;
- aggregate top-products reporting;
- passing report tests.

---

## Recap in One Diagram

```text
PHASE 8

existing models
   ↓
report service
   ↓
aggregate SQL + snapshots
   ↓
admin-only report routes
   ↓
API tests
```

---

## Why This Phase Matters

Phase 8 turns the backend from “stores data” into “explains data.”

That is important because employers like seeing backend code that does more than CRUD. Reports show that you understand:

- SQL aggregation,
- response shaping,
- data correctness,
- access control,
- async ORM behavior,
- and end-to-end test coverage.

That makes the project feel much more complete and much more production-like.
