# Phase 10.5 Recap — Order Management UI & Formatting Tooling

## What Is Covered

This is **Part 5** of Phase 10. It covers the last feature built so far — the order management UI — and one piece of tooling that was added first because a real formatting problem had appeared.

The work had four connected pieces:

1. an audit of what the backend already offered but nothing was using;
2. Prettier, added in response to actual style drift;
3. the orders API module and a multi-line-item order form;
4. the orders page, with inline expansion and admin-only cancellation.

```text
PART 1
Audit — what is built and unused?

PART 2
Prettier — stop style drift with a tool, not vigilance

PART 3
api/orders.ts + OrderForm (dynamic line items)

PART 4
OrdersPage — list, expand, cancel
```

---

## Big Picture

```text
Before
  the entire orders API existed and had zero frontend callers
  the whole reports API likewise
  ProductsPage was 4-space indented; every other file was 2-space
  nothing enforced formatting

After
  Orders tab: place an order, view its line items, cancel it
  Prettier enforcing one style across the frontend
  reports API still unused — documented as remaining work
```

---

## Why This Part Matters

Two different lessons sit side by side here.

The feature work shows what happens when a backend is built ahead of its client: a complete, tested, well-designed orders API sat unused for months, and connecting it took four files.

The tooling work shows the difference between fixing an instance of a problem and fixing the cause of it.

---

## Part 1 — The Audit

Before building, the backend was surveyed for endpoints with no frontend caller. It found two whole features:

```text
Orders — entirely unused
  POST   /orders               create (any authenticated user)
  GET    /orders               paginated list (any user)
  GET    /orders/{id}          single order (any user)
  PATCH  /orders/{id}/cancel   cancel (admin only, restores stock)

Reports — entirely unused, all admin-only
  GET /reports/stock-summary
  GET /reports/low-stock
  GET /reports/top-products
  GET /reports/movement-history

Partial gaps
  GET /products?include_inactive=true  — supported, never called
```

### The unreachable status

The audit also turned up a genuine design gap. `OrderStatus` has three values:

```python
class OrderStatus(PyEnum):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
```

But **no endpoint ever sets `FULFILLED`**. Orders can only travel `PENDING → CANCELLED`. The third state exists in the enum and in the database and is unreachable.

The decision was to build the UI for what the API actually supports and record the gap, rather than fake a status transition client-side or expand the scope mid-feature.

```text
Option taken:     build for reality, document the gap
Option rejected:  add PATCH /orders/{id}/fulfill now (scope creep)
Option rejected:  show a status the backend can never produce (a lie in the UI)
```

That is the honest way to handle an inconsistency found mid-build: name it, decide deliberately, move on.

---

## Part 2 — Prettier

### The trigger

`ProductsPage.tsx` had been written with 4-space indentation while `ProductCard.tsx`, `StockPage.tsx`, and `MovementsPage.tsx` were all 2-space. Nothing was functionally wrong. But the codebase now had two competing styles and **no tool that would catch the next drift**.

ESLint was already configured, but ESLint checks code quality, not indent width.

### The choice

```text
Option A: hand-fix ProductsPage.tsx back to 2-space
  -> fixes this instance
  -> nothing prevents the next one

Option B: add Prettier + reformat once
  -> fixes this instance
  -> and removes the class of problem
```

Option B was taken because the root cause was the absence of enforcement, not the presence of one badly indented file.

### The config

```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2
}
```

Three keys, not thirty. Everything else Prettier defaults to already matched the existing code, so overriding it would be config that exists to restate the default — more to maintain, nothing gained.

Critically, the config was written to match **the style already in the codebase**, not a preferred style imported from elsewhere. A formatter configured against the grain of existing code produces an enormous, unreviewable first diff.

### Two scripts, two purposes

```json
"format": "prettier --write .",
"format:check": "prettier --check ."
```

```text
--write  -> rewrites files (the one-time cleanup, and routine use)
--check  -> reports mismatches, changes nothing (CI-shaped)
```

### The reformat, and how it was committed

The one-time `npm run format` touched 20 source files. `ProductsPage.tsx` accounted for 441 changed lines — the indent rewrite — while everything else was small quote and trailing-comma nits.

That was committed **on its own**, separate from feature work. Mixing a whole-repo reformat into a feature commit makes the feature diff unreviewable: hundreds of whitespace-only lines bury the handful of lines that actually changed behaviour.

```text
one commit: "added .prettier and applied in the code"
then:       feature commits, readable again
```

### It does not come free afterwards

Worth recording: while building the orders feature, two hand-edited files (`App.tsx`, `AppHeader.tsx`) still failed `format:check`. Matching the surrounding style by eye is not the same as matching the formatter. Running `npm run format` after hand-writing files is now part of the loop.

---

## Part 3 — The Orders API Module and Form

### Types mirror the backend schemas

`api/orders.ts` follows the template from `products.ts` and `stock.ts`. The one thing worth noting is the money fields again:

```ts
export type OrderItem = {
  quantity: number
  unit_price: string   // Decimal -> JSON string
  subtotal: string     // Decimal -> JSON string
  ...
}
```

Same reasoning as `Product.price` in Part 2: `Decimal` serialises to a string so the exact value survives the wire, and the frontend converts only for display.

### The new UI problem: dynamic line items

Every form so far had a fixed set of fields. An order has a variable number of line items, so the form's state is an **array**:

```ts
type LineState = {
  product_id: string
  quantity: string
}

const [lines, setLines] = useState<LineState[]>([emptyLine()])
```

with three operations over it:

```ts
const updateLine = (index: number, field: keyof LineState, value: string) => {
  setLines((prev) =>
    prev.map((line, i) => (i === index ? { ...line, [field]: value } : line)),
  )
}

const addLine = () => setLines((prev) => [...prev, emptyLine()])

const removeLine = (index: number) =>
  setLines((prev) => prev.filter((_, i) => i !== index))
```

All three build a **new array** rather than mutating the existing one. React decides whether to re-render by comparing references; mutating `lines` in place and calling `setLines(lines)` passes the same reference, and the screen does not update.

```text
prev.map(...) / [...prev, x] / prev.filter(...)
  -> new array, new reference -> React re-renders

lines[i].quantity = '5'; setLines(lines)
  -> same reference -> no re-render
```

### Index as the React key — and why it is safe here

```tsx
{lines.map((line, index) => (
  <div key={index}>...</div>
))}
```

Using an array index as a `key` is normally a smell. Keys are how React tells list items apart between renders — like a coat check ticket. If ticket numbers stay attached to the same coats, everything is fine; if two coats swap ticket numbers, someone gets the wrong coat back.

Remove the middle row of `[A, B, C]` and the array becomes `[A, C]`. With index keys, `key=1` used to mean B and now means C. React sees "an item still exists at key 1" and reuses that DOM node rather than unmounting B and mounting C — the ticket number stayed put while the coat underneath changed.

It is safe in this form for a specific reason: **every field is a controlled input**. `value={line.product_id}` and `value={line.quantity}` are driven entirely from React state, so even when React reuses the wrong physical node, it overwrites that node's value from props on the same render. Nothing stale can be displayed.

```text
The index-key bug bites when a row holds its OWN state:
  - useState inside the row component
  - an uncontrolled input using defaultValue
Both live on the DOM node and survive the swap.

This form has neither.
```

The only cost is cosmetic: deleting a row while typing in a later one can make keyboard focus appear to jump.

### Validating duplicates client-side

```ts
const seen = new Set<string>()

for (const line of lines) {
  if (seen.has(line.product_id)) {
    setError('Each product can only appear once — combine quantities into one line.')
    return
  }
  seen.add(line.product_id)
  ...
}
```

This mirrors the backend's `no_duplicate_products` validator in `OrderCreate` almost exactly. The duplication is deliberate and one-directional:

```text
Backend check  -> the boundary that matters; anyone can POST directly with curl
Frontend check -> instant, specific feedback instead of a round trip and a generic 400
```

Deleting the frontend copy would cost UX. Deleting the backend copy would cost data integrity.

A `Set` is the right structure because it holds each value once and answers `has()` in constant time — exactly the "have I seen this already?" question being asked.

---

## Part 4 — The Orders Page

### The detail-view decision

Two options for showing an order's line items: expand inline in the table, or navigate to `/orders/:id`.

Inline expansion was chosen because an order has a handful of line items — not enough content to justify a route, a page component, and a navigation round trip. It also reuses the exact interaction `ProductsPage` already established for inline editing, so the app behaves consistently.

```tsx
const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null)

const toggleExpand = (orderId: string) => {
  setExpandedOrderId((prev) => (prev === orderId ? null : orderId))
}
```

A single `string | null` rather than a `Set` means only one order can be open at a time — setting a new id replaces the old one, so two rows cannot both be expanded. Same reasoning as one-row-at-a-time editing on the products table: the page cannot grow unbounded as the user clicks around.

### Totals are computed, not stored

```tsx
const orderTotal = (order: Order) =>
  order.items.reduce((sum, item) => sum + Number(item.subtotal), 0)
```

The `Order` model has no `total` column. `OrderItem.subtotal` is itself a `@property` computed as `quantity × unit_price`, never persisted.

That is a deliberate backend choice: a stored total is a value that can drift out of sync with the rows it summarises. The frontend follows the same principle rather than inventing a cached number of its own.

```text
Derive it   -> always consistent with its inputs
Store it    -> a second source of truth that can disagree
```

### Loading products only when the form opens

```tsx
const openCreateForm = async () => {
  setFormError('')
  setShowForm(true)
  try {
    const data = await getProducts(1, 100)
    setProducts(data.items)
  } catch (err) {
    setFormError(getErrorMessage(err, 'Failed to load products.'))
  }
}
```

The product dropdown needs products, but only when someone is actually placing an order. Fetching them on page mount would cost every visitor a request they will usually not need. No new backend endpoint was required — the existing paginated list with a large page size covers it.

The dropdown shows live stock, so the user can see what is available while choosing:

```tsx
{product.sku} — {product.name} ({product.quantity} in stock)
```

### Cancellation is admin-only, on both ends

```tsx
const canCancel = user?.is_admin && order.status === 'PENDING'
```

matching the backend:

```python
current_user: User = Depends(get_current_admin)
```

and the service rule that only `PENDING` orders may be cancelled — cancelling an already-cancelled order would restore stock twice.

This means the user who *placed* an order cannot cancel it themselves; only an admin can. That was reviewed explicitly and kept, on the grounds that stock-affecting actions have one clear authority. Changing it later would require both loosening the backend dependency to `get_current_user` **and** adding an `order.created_by == current_user.id or current_user.is_admin` check — the frontend condition alone would be theatre.

### What cancelling actually triggers

Worth remembering when reading the UI code, because one button does a lot:

```text
PATCH /orders/{id}/cancel
  ↓
for each item: StockService.adjust_stock(RECEIVE, +quantity, commit=False)
  ↓
order.status = CANCELLED
  ↓
single commit — all items restored or none
  ↓
cache invalidation: products:list:*, stock:history:*, stock:movements:*
```

Items whose product was hard-deleted are logged and skipped rather than crashing the cancellation.

---

## What Changed in the Project

```text
frontend/
  .prettierrc                         -> semi:false, singleQuote:true, tabWidth:2
  .prettierignore                     -> dist, node_modules
  package.json                        -> format / format:check scripts
  src/api/orders.ts                   -> types + createOrder/cancelOrder/getOrders
  src/components/orders/OrderForm.tsx -> dynamic line-item form
  src/pages/OrdersPage.tsx            -> list, inline expand, cancel, pagination
  src/components/layout/AppHeader.tsx -> Orders tab
  src/App.tsx                         -> /orders route
```

No backend changes. The orders API was already complete — this part was purely about connecting it.

---

## Technical Lessons

### 1. Fix the cause, not the instance

One badly indented file was the symptom. The absence of a formatter was the cause.

### 2. Configure a formatter to match existing code

Otherwise the first run produces a diff nobody can review.

### 3. Commit mechanical reformats separately

A 441-line whitespace change inside a feature commit hides the feature.

### 4. Always produce new arrays in React state updates

`map` / `filter` / spread. Mutating in place gives React the same reference and no re-render.

### 5. Index keys are safe only with fully controlled inputs

The classic bug needs per-row internal state to bite. Know which case you are in rather than applying the rule blindly.

### 6. Duplicate validation across the boundary on purpose

Frontend for speed and specificity, backend for integrity. They are not redundant; they serve different goals.

### 7. Derive totals, do not store them

A stored aggregate is a second source of truth that can disagree with its inputs.

### 8. Fetch on demand, not on mount

The product list for the order dropdown is only needed when the form opens.

### 9. An audit before building is cheap and finds real gaps

It surfaced two entirely unused features and one unreachable enum value.

---

## Final State After This Part

- Prettier enforcing one style across the frontend, with a check script for CI;
- `api/orders.ts` covering create, cancel, and paginated list;
- `OrderForm` with dynamic line items, client-side duplicate detection, and live stock in the dropdown;
- `OrdersPage` with status badges, computed totals, inline line-item expansion, admin-only cancellation, and pagination;
- an Orders tab in `AppHeader` and an `/orders` route;
- frontend typecheck clean, 88/88 backend tests passing.

### Known gaps, deliberately not built

```text
FULFILLED status         -> in the enum, no endpoint sets it
Order creators cannot cancel their own orders -> admin-only, reviewed and kept
GET /reports/*           -> four admin endpoints, still no frontend caller
include_inactive=true    -> supported by the API, never requested by the UI
Movements: stock vs order source -> not distinguishable except by a free-text note;
                                    would need a nullable order_id FK on stock_movements
```

Remaining Phase 10 work: the low-stock dashboard and a reports UI.

---

## Recap in One Diagram

```text
PHASE 10.5

AppHeader ── Products ── Movements ── Orders
                                        │
                                        ↓
                              GET /api/v1/orders?page=
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                   New order (any user)        Order row
                          │                           │
              GET /products (on open)      ┌──────────┼──────────┐
                          │                │          │          │
                   OrderForm            View       Cancel     total =
                   ├ customer_name      items     (admin +      Σ subtotal
                   ├ line: product+qty     │      PENDING)      (computed)
                   ├ + Add item            │          │
                   └ Set-based dup check   ↓          ↓
                          │           expand <tr>  PATCH /orders/:id/cancel
                          ↓           line items         │
                   POST /api/v1/orders                   ↓
                          │                     RECEIVE movements per item
                   validate stock                        │
                   snapshot name/sku/price         status = CANCELLED
                   SHIP movements                        │
                   single atomic commit            invalidate caches
```