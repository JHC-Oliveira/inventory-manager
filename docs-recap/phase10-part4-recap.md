# Phase 10.4 Recap — Stock Adjustment UI & Navigation Restructure

## What Is Covered

This is **Part 4** of Phase 10 and the largest single stretch of the frontend work — fifteen commits. It started as "add a stock adjustment screen" and grew into a restructure of the whole application's navigation, plus two genuinely instructive bugs.

The work had six connected pieces:

1. a per-product stock page combining an adjustment form and movement history;
2. a **new backend endpoint**, because no "all movements" query existed;
3. splitting the single dashboard into Products and Movements tabs behind a shared header;
4. redesigning the product list from a card grid into a table with inline editing;
5. a real cache-invalidation bug that served stale quantities;
6. a table-layout bug that took two attempts to diagnose correctly.

```text
PART 1
/products/:id/stock — adjust stock, see that product's history

PART 2
GET /stock/movements — history across all products (new backend work)

PART 3
Products and Movements as separate tabs, shared AppHeader

PART 4
Product cards become table rows with inline expand-to-edit

PART 5
Bug: stale quantities after an adjustment

PART 6
Bug: uneven table columns (diagnosed wrong the first time)
```

---

## Big Picture

```text
Before
  one DashboardPage doing everything
  stock adjustment only possible through Swagger
  movement history only queryable per product
  product cards in a grid — fine at 6 products, unusable at 60

After
  AppHeader with Products / Movements tabs
  /products/:id/stock for adjustments + per-product history
  /movements for global, filterable history
  products as a compact table with inline edit
  /dashboard redirects to /products
```

---

## Why This Part Matters

This is where the frontend stopped being a thin CRUD wrapper and started making genuine product decisions: how a user navigates, when a card should become a row, and what happens to a cache when data changes underneath it.

It is also the part where the frontend work **drove backend work** — the UI needed a query the API could not answer.

---

## Part 1 — The Stock Adjustment Page

### Scope decision

The adjustment form and the movement history were combined onto **one page per product** (`/products/:id/stock`) rather than split across a modal and a separate history view. Adjusting stock and seeing the result are the same task; separating them would mean navigating away to confirm the thing you just did.

```text
/products/:id/stock
  ├── header: product name, SKU, current quantity
  ├── adjust form   (admins only)
  └── movement history (any authenticated user), paginated
```

### The domain rule that shaped the form

`schemas/stock_movement.py` enforces sign rules per movement type:

```text
RECEIVE  -> quantity_change must be positive   (stock coming in)
SHIP     -> quantity_change must be negative   (stock going out)
ADJUST   -> either sign allowed                (manual correction, both ways)
```

Making the user work out the sign themselves would guarantee 400s. The form absorbs the rule instead:

```tsx
if (form.movement_type !== 'ADJUST' && quantityNum < 0) {
  setFormError('Enter a positive quantity — the sign is applied automatically.')
  return
}

const signedQuantity =
  form.movement_type === 'SHIP' ? -Math.abs(quantityNum) : quantityNum
```

```text
RECEIVE 10  -> user types 10  -> sends +10
SHIP    10  -> user types 10  -> sends -10   (sign applied for them)
ADJUST -3   -> user types -3  -> sends -3    (signed input allowed)
```

`-Math.abs(...)` rather than negation is defensive: it produces the right value whether the user typed `10` or `-10`.

The rule is also stated in the UI as helper text, so the behaviour is discoverable rather than magic.

### Reloading everything after a successful adjustment

```tsx
await adjustStock(id, { ... })
setForm({ movement_type: 'RECEIVE', quantity: '', note: '' })
await loadAll()
```

`loadAll()` refetches **both** the product and the first page of history, because an adjustment changes both — the quantity in the header and the new row at the top of the list. Refetching only the history would leave a stale quantity on screen.

---

## Part 2 — A New Backend Endpoint

### The gap

The Movements tab needed "every movement across all products, newest first, optionally filtered by type." The existing `GET /stock/{product_id}/history` could not answer that — it is scoped to one product by design.

This is worth naming: the frontend requirement was legitimate, and the correct response was to add a proper endpoint rather than have the UI fetch every product and stitch histories together client-side.

### `StockService.get_all_movements`

```python
query = select(StockMovement)
if movement_type is not None:
    query = query.where(StockMovement.movement_type == movement_type)

count_result = await self.db.execute(
    select(func.count()).select_from(query.subquery())
)
total = count_result.scalar_one()
```

### Why `select_from(query.subquery())`

The count must respect the **same filter** as the page query. Writing a second, separate count query means two places that must be kept in sync — and the day someone adds a filter to one and forgets the other, pagination silently reports wrong totals.

Wrapping the already-filtered query as a subquery and counting that guarantees they can never diverge. This idiom was not invented here — it was copied from `product_service.get_products`, which already solved the same problem.

```text
Two independent queries -> two places to update -> drift
count(subquery of the real query) -> one source of truth
```

### Route placement

```python
@router.get("/movements", ...)          # 2 segments
@router.get("/{product_id}/history")    # 3 segments
@router.post("/{product_id}/adjust")    # 3 segments
```

`/stock/movements` cannot be shadowed by `/stock/{product_id}/...` because the path shapes differ in segment count — there is no `{product_id}` slot that `movements` could be swallowed by.

### Caching, added from the start

```python
cache_key = f"stock:movements:{page}:{page_size}:{movement_type}"
```

Every parameter that changes the result is part of the key. Omitting `movement_type` would mean a RECEIVE-filtered request could be served from an unfiltered cache entry — the classic cache-key bug.

The same 60-second TTL (`STOCK_HISTORY_CACHE_TTL`) as the existing per-product history was reused rather than a new value invented.

---

## Part 3 — Navigation Restructure

### The problem

`DashboardPage` was doing three jobs: it *was* the product list, it owned the header and logout, and it was the only place to land after login. Adding a Movements view had nowhere to go.

### The split

```text
DashboardPage.tsx  (deleted)
  ├──> AppHeader.tsx     — nav tabs, user name, logout
  ├──> ProductsPage.tsx  — the product list
  └──> MovementsPage.tsx — global movement history
```

`/dashboard` became a redirect to `/products` rather than a 404, so old links and any muscle memory still work:

```tsx
<Route path="/dashboard" element={<Navigate to="/products" replace />} />
```

### Why `AppHeader` was extracted when it was

The header was pulled into its own component at the moment it had **two real call sites**, not before.

```text
Extract on speculation -> an abstraction shaped by one use case,
                          which the second use case then fights

Extract on the second real use -> the shared shape is known, not guessed
```

### Active tab detection

```tsx
location.pathname.startsWith(tab.to)
```

`startsWith` rather than `===` so that `/products/prd_123/stock` still highlights the Products tab. A user drilled into a sub-page should still see where they are in the navigation.

### The filter on MovementsPage

```tsx
useEffect(() => {
  loadMovements(1, filter)
}, [filter])
```

The dependency array is doing real work here: changing the filter re-runs the effect automatically, and resetting to page 1 is deliberate — page 4 of "all movements" is meaningless as page 4 of "RECEIVE only".

Deleted products are handled explicitly, since `product_id` is nullable after a hard delete:

```tsx
{m.product_id ? (
  <Link to={`/products/${m.product_id}/stock`}>{m.product_sku}</Link>
) : (
  <span>{m.product_sku} (deleted)</span>
)}
```

The SKU snapshot on the movement row means history stays readable even when the product record is gone — the backend's snapshot design paying off in the UI.

---

## Part 4 — Cards Become Rows

### The problem

The card grid looked good with six products and would be unusable with sixty — each card was tall, and scanning quantities across a grid is much harder than reading a column.

### The change

`ProductCard` was rewritten to return a `<tr>` instead of an `<article>`, and gained a `Low stock` column. Clicking **Edit** expands `ProductForm` inline beneath that specific row:

```tsx
<Fragment key={product.id}>
  <ProductCard ... isEditing={isEditing} onEdit={() => handleEditClick(product)} />

  {isEditing && (
    <tr>
      <td colSpan={6}>
        <ProductForm mode="edit" initialData={selectedProduct} ... />
      </td>
    </tr>
  )}
</Fragment>
```

### Why `<Fragment>` and not `<>`

Each product renders **two sibling elements** (the row, and conditionally the expanded row) and the list needs a `key`. The shorthand `<>...</>` cannot take a `key`; the explicit `Fragment` can.

```text
<>...</>        -> no key allowed
<Fragment key>  -> groups siblings AND carries the key
```

### The payoff from Part 2's design

`ProductForm` did not need a single change to work inside a table cell. Because it takes `onSubmit`/`onCancel` callbacks and never calls the API itself, the page could relocate it from a top panel into an expanded row and it simply worked. That is the concrete return on the "form owns fields, page owns behaviour" split.

### Toggle behaviour

```tsx
const handleEditClick = (product: Product) => {
  if (showForm && formMode === 'edit' && selectedProduct?.id === product.id) {
    closeForm()
  } else {
    openEditForm(product)
  }
}
```

Clicking Edit on the already-open row closes it; clicking Edit on a different row moves the form there. The button label follows (`Edit` / `Cancel`) so the control always describes what it will do.

---

## Part 5 — The Stale Quantity Bug

### The symptom

Adjust stock on a product, go back to the products list, and the old quantity was still shown. Waiting a few minutes fixed it on its own.

### The root cause

"Fixes itself after a few minutes" is the signature of a cache TTL, not a database problem. `adjust_stock` was updating `product.quantity` in the database and invalidating the **stock history** cache — but never the **products list** cache. The list kept serving its cached page until the 5-minute TTL expired.

```text
adjust_stock
  ├── UPDATE products.quantity        ✅
  ├── INSERT stock_movement           ✅
  ├── invalidate stock:history:*      ✅
  └── invalidate products:list:*      ❌  <- missing
```

### The fix

```python
if commit:
    await cache_delete_pattern(f"stock:history:{product_id}:*")
    await cache_delete_pattern(PRODUCTS_CACHE_PATTERN)      # added
    await cache_delete_pattern(ALL_MOVEMENTS_CACHE_PATTERN) # added
```

Importing `PRODUCTS_CACHE_PATTERN` from `product_service` rather than re-typing the string keeps one definition of what that key space is called.

### The real lesson

The project rule from Phase 7 is *"cache with explicit invalidation — never serve stale data for speed."* The failure was not the rule; it was applying it only to the cache the author was thinking about at the time.

```text
The question to ask on every write path:
  "which caches could this write have made wrong?"
  — not "which cache am I currently working on?"
```

A write that touches products must invalidate every view of products, not just the one nearest the code being edited.

### Test impact, twice

`test_adjust_stock_invalidates_history_cache` asserted the invalidation happened **exactly once**:

```python
mock.assert_awaited_once_with("stock:history:prd_1:*")
```

Adding the products invalidation broke it — correctly. It was updated to count and check each pattern:

```python
assert mock.await_count == 2
mock.assert_any_await("stock:history:prd_1:*")
mock.assert_any_await("products:list:*")
```

Then adding the global movements cache broke it again, taking the count to 3. Both breakages were the test doing its job: a test that pins down *how many* caches are cleared will always notice when a new one is added, which is exactly the moment to check the new one is correct.

---

## Part 6 — The Table Layout Bug

This bug is worth recording because the **first diagnosis was wrong**, and the reason it was wrong is a genuine misunderstanding of how HTML tables size themselves.

### Attempt 1 — `whitespace-nowrap`

Symptom: uneven, oddly large gaps between columns. First theory: columns were wrapping and taking more room than needed. Fix applied: `whitespace-nowrap` on every column except the flexible one.

Result: **still broken.**

### Attempt 2 — the actual cause

The real cause is the default table layout algorithm. `table-auto` does **not** give leftover width to one flexible column. It distributes leftover space *proportionally across all columns*, based on their content widths — including columns with real content, like an Actions column full of buttons.

`whitespace-nowrap` only sets a **minimum** width floor. It says "do not shrink below this." It says nothing about how surplus space is shared out, which was the actual problem.

```text
table-auto (default)
  -> browser measures content
  -> distributes surplus width proportionally to ALL columns
  -> the widest content column absorbs the most
  -> unexplained dead space

table-fixed + explicit widths
  -> declared widths are obeyed exactly
  -> the one column WITHOUT a width absorbs 100% of the remainder
  -> deterministic
```

### The fix

```tsx
<table className="w-full table-fixed text-left text-sm">
  <th className="px-4 py-3">Product</th>                        {/* no width -> flexes */}
  <th className="w-28 px-4 py-3 whitespace-nowrap">Quantity</th>
  <th className="w-28 px-4 py-3 whitespace-nowrap">Price</th>
  <th className="w-28 px-4 py-3 whitespace-nowrap">Status</th>
  <th className="w-28 px-4 py-3 whitespace-nowrap">Low stock</th>
  <th className="w-72 px-4 py-3 whitespace-nowrap">Actions</th>
```

### The debugging lesson

The first fix targeted a plausible-sounding symptom without confirming the mechanism. It changed the rendering slightly, which made it *look* partially effective, which is the most misleading kind of wrong fix.

```text
"This might cause it" + "the output changed a bit"
  -> not the same as understanding the cause

Reproduce -> explain the mechanism -> then fix
```

### A third, smaller bug

The product name had no left padding: the `<td>` used `py-3 pr-4` (padding right only) while the header `<th>` used `px-4` (both sides). Header and body cells were styled independently and drifted. Fixed by matching them.

---

## Part 7 — Long Text and Dates

### Truncation over input limits

Long notes broke the table layout. Two options: cap the input length, or clip the display.

Clipping won, on the principle that **display problems should be fixed at the display layer**. Limiting input would destroy information the user meant to record, to solve a CSS problem — the same reasoning behind `git log --oneline`: the full commit message still exists, one view just chooses to show less of it.

```tsx
<td className="max-w-[200px] truncate" title={m.note ?? undefined}>
  {m.note ?? '—'}
</td>
```

Tailwind's `truncate` is `overflow-hidden` + `text-overflow: ellipsis` + `white-space: nowrap`. The native `title` attribute gives the full text back on hover — no tooltip library needed.

### Dates

```tsx
{new Date(m.created_at).toLocaleDateString('en-GB')}
```

`en-GB` produces `dd/mm/yyyy` natively. No date library was added for a format the platform already provides.

---

## Part 8 — The Missing Pagination

The products list was calling `getProducts(1, 12)` with the page number hardcoded and no Previous/Next controls at all — a pre-existing gap inherited from `DashboardPage`, invisible while there were fewer than 12 products.

The fix applied the same pagination shape already used on `StockPage` and `MovementsPage`:

```text
page / totalPages state
loadX(targetPage) sets both from the response
Previous / Next buttons, disabled at the boundaries
rendered only when totalPages > 1
```

The subtle part is which page to return to after a write:

```tsx
await loadProducts(formMode === 'create' ? 1 : page)  // create -> page 1
await loadProducts(page)                              // delete -> stay put
```

A newly created product appears at the top of a newest-first list, so jumping to page 1 shows the user what they just made. A deletion or edit should not move them.

---

## What Changed in the Project

```text
backend/
  app/services/stock_service.py -> get_all_movements() + caching
                                   adjust_stock now invalidates 3 patterns
  app/routers/stock.py          -> GET /stock/movements
  tests/test_stock.py           -> invalidation assertions updated twice

frontend/src/
  api/stock.ts                  -> adjustStock, getStockHistory, getAllMovements
  api/products.ts               -> getProduct(id)
  pages/StockPage.tsx           -> per-product adjust + history
  pages/ProductsPage.tsx        -> table layout, inline edit, pagination
  pages/MovementsPage.tsx       -> global filterable history
  components/layout/AppHeader.tsx -> shared nav
  components/products/ProductCard.tsx -> rewritten as a table row
  pages/DashboardPage.tsx       -> deleted
  App.tsx                       -> /products, /movements, /products/:id/stock
```

---

## Technical Lessons

### 1. Invalidate every cache a write could have staled

Ask "what views of this data exist?", not "which cache am I looking at?"

### 2. "It fixes itself after a few minutes" means TTL

That symptom points at caching before anything else.

### 3. `table-auto` shares surplus width proportionally

It does not hand it to one column. `table-fixed` plus explicit widths on all but one column is the deterministic fix; `whitespace-nowrap` only sets a floor.

### 4. Confirm the mechanism before fixing

A plausible fix that changes the output slightly is the most misleading kind of wrong.

### 5. Count the filtered query, do not rewrite it

`select(func.count()).select_from(query.subquery())` guarantees the count and the page always agree.

### 6. Every parameter that changes a result belongs in the cache key

Leaving `movement_type` out would serve filtered requests from unfiltered entries.

### 7. Fix display problems at the display layer

Truncate with CSS; do not amputate the user's data to satisfy a layout.

### 8. Extract a shared component on the second real use

`AppHeader` was extracted when two pages genuinely needed it — not in anticipation.

### 9. Callback-driven components relocate for free

`ProductForm` moved from a page panel into a table cell with zero changes, because it never owned its own submit behaviour.

---

## Final State After This Part

- `/products/:id/stock` with an admin-gated adjustment form and paginated history;
- automatic sign handling that encodes the RECEIVE/SHIP/ADJUST domain rule;
- a new `GET /stock/movements` endpoint with filtering, pagination, and caching;
- `AppHeader` with Products/Movements tabs, `/dashboard` redirecting to `/products`;
- the product list as a compact `table-fixed` table with an inline expanding edit row;
- correct cache invalidation across all three affected key spaces;
- working pagination on all three list views;
- 88/88 backend tests passing, frontend typecheck clean.

---

## Recap in One Diagram

```text
PHASE 10.4

AppHeader ── Products ── Movements
                │            │
                │            └─> GET /stock/movements?movement_type=&page=
                │                 (new endpoint, cached, filtered count)
                │
                └─> ProductsPage (table-fixed)
                      │
                      ├─ Edit ──> expands ProductForm inline in a <tr>
                      ├─ Delete ──> confirm ──> reload current page
                      └─ Manage stock ──> /products/:id/stock
                                              │
                                              ├─ adjust form (admin)
                                              │    RECEIVE/SHIP -> sign applied
                                              │    ADJUST       -> signed input
                                              │        ↓
                                              │    POST /stock/:id/adjust
                                              │        ↓
                                              │    invalidate:
                                              │      stock:history:{id}:*
                                              │      products:list:*        <- the bug fix
                                              │      stock:movements:*
                                              │        ↓
                                              └─ reload product + history
```