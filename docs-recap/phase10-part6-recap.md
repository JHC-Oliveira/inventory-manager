# Phase 10.6 Recap — Dashboard, Reports & The Bugs Underneath

## What Is Covered

This is **Part 6** of Phase 10 — the last two admin pages, plus three bugs that were only found because the pages got built and used.

The work had six connected pieces:

1. an audit that found two entire backend features with no frontend caller;
2. rejecting a wireframe that duplicated its own widgets;
3. building Dashboard and Reports behind an admin gate;
4. merging two movement views that had drifted apart;
5. a UTC-versus-local-time bug that made a working filter look broken;
6. discovering the project's typecheck had been checking nothing, and its build had never succeeded.

```text
PART 1
Audit — what's built and unused?

PART 2
Two pages, not three — killing duplicated widgets

PART 3
Admin gating, and the redirect loop waiting in it

PART 4
One movements page, both filters

PART 5
Filtering in UTC, displaying in local — the day-boundary bug

PART 6
The verification that verified nothing
```

---

## Big Picture

```text
Before
  four /reports/* endpoints, zero callers
  /dashboard redirected to /products
  ProtectedRoute.adminOnly existed, never used
  movement history split across two pages, two filter types
  npm run build had never succeeded
  tsc --noEmit passed on everything, always

After
  /dashboard — KPI tiles + full low-stock table (admin)
  /reports — stock summary + top products (admin)
  role-filtered nav tabs
  /movements — one table, type AND date filters
  dates filtered in the user's timezone
  a production build that works
  an index on the column every movement query sorts by
```

---

## Why This Part Matters

Every bug in this part was invisible from reading code. They surfaced from **using** the app and from **checking claims against reality**:

```text
"the filter isn't working"        -> found a timezone bug
"why is this on two pages?"       -> found a design duplication
"VS Code is complaining"          -> found the typecheck was fake
```

That is the actual lesson of this part: verification you haven't tested is a guess.

---

## Part 1 — The Audit

Before building, the backend was surveyed for endpoints nothing called. It found two complete features:

```text
/reports/stock-summary     per-product inventory value + totals
/reports/low-stock         active products at or below threshold
/reports/top-products      order aggregates: units, orders, revenue
/reports/movement-history  movements, date-range filtered, paginated
```

All four admin-only. All four with no frontend caller since Phase 8.

The audit also surfaced two things worth naming before writing any UI:

**`ProtectedRoute.adminOnly` had never been used.** Built in Part 1 of Phase 10, zero call sites since. Every reports endpoint is admin-gated, so this was finally its moment.

**`get_top_products` counts cancelled orders.** It aggregates `OrderItem` with no join to `Order` and no status filter, so a cancelled order still contributes to "top product" revenue. Left as a known bug, with a caption in the UI stating it — the honest option when the number can't be trusted yet.

---

## Part 2 — Two Pages, Not Three

A wireframe from an earlier review specified three screens: Dashboard, Low Stock, and Reports. Building to it would have been the obedient choice. Mapping the widgets against the endpoints showed why it was wrong:

```text
Dashboard      KPI tiles + top products + "recent low-stock alerts"
Low Stock      low-stock table                  <- full version of a Dashboard widget
Reports        stock summary + top products     <- same widget as Dashboard
                                + movement history
```

Two of the three Dashboard widgets were previews of pages sitting next to them in the nav. And `stock-summary` already returns `is_low_stock` and `low_stock_threshold` per row — the low-stock report is that same data with a filter, not a different kind of thing.

The nav would have reached **six tabs** for an app with four entities.

**What was built instead:**

```text
/dashboard   what needs attention now
             KPI tiles + the FULL low-stock table (short by nature, no preview needed)

/reports     analysis
             stock summary + top products
```

Top products moved to Reports, where it belongs — all-time revenue analysis, not something you act on today. Nothing appears twice. Five tabs.

### The lesson

A wireframe is a proposal, not a specification — including one you wrote yourself earlier. The question "is this actually the best structure?" was asked *before* the code existed, which is the cheapest possible moment to change the answer.

---

## Part 3 — Admin Gating and the Latent Redirect Loop

Every tile on both new pages is fed by an admin-only endpoint. A non-admin loading `/dashboard` would have seen four 403s, so the gate had to match the data.

### The bug found before it could bite

```tsx
// ProtectedRoute.tsx — as written in Phase 10.1
if (adminOnly && !user?.is_admin) return <Navigate to="/dashboard" replace />
```

The guard's rejection target was `/dashboard`. The moment `/dashboard` itself became admin-gated, a non-admin hitting it would be redirected to `/dashboard`, which would reject them, which would redirect them to `/dashboard` — forever.

It had been latent since Phase 10.1 purely because `adminOnly` had never had a call site.

```tsx
if (adminOnly && !user?.is_admin) return <Navigate to="/products" replace />
```

**The rule:** a guard's fallback must point somewhere the rejected user is actually allowed to be. Otherwise the guard doesn't terminate.

### Nested guards

```tsx
<Route element={<ProtectedRoute />}>
  <Route element={<ProtectedRoute adminOnly />}>
    <Route path="/dashboard" element={<DashboardPage />} />
    <Route path="/reports" element={<ReportsPage />} />
  </Route>

  <Route path="/products" element={<ProductsPage />} />
  ...
</Route>
```

The outer guard checks `accessToken` and renders `<Outlet />`; the inner one runs inside that outlet and adds the `is_admin` check. A logged-out visitor never reaches the admin check at all.

### Role-filtered tabs

```tsx
const visibleTabs = tabs.filter((tab) => !tab.adminOnly || user?.is_admin)
```

Computed inside the component, not at module scope — the `tabs` constant is evaluated once at import, before anyone has logged in. Same "read state at call time, not import time" rule as the axios interceptor in Phase 10.1.

---

## Part 4 — Merging the Two Movement Views

### How the duplication was found

Not by review — by using the built page and asking *"why is there movement history in reports if I already have it on movements?"*

```text
                /movements                  /reports movement section
endpoint        GET /stock/movements        GET /reports/movement-history
filter          by TYPE                     by DATE RANGE
access          any authenticated user      admin only
columns         identical                   identical
```

Same table, two filter axes, two pages. A user wanting "all SHIP movements in January" could not get it anywhere — they had to pick which half of the question to ask.

### The fix

Add date filtering to the endpoint that already had type filtering, rather than the reverse — `/stock/movements` was already the any-user endpoint with the filter UI built.

```python
if movement_type is not None:
    query = query.where(StockMovement.movement_type == movement_type)
if start_date is not None:
    query = query.where(StockMovement.created_at >= start_date)
if end_date is not None:
    query = query.where(StockMovement.created_at <= end_date)
```

### The cache key had to grow with the filters

```python
cache_key = (
    f"stock:movements:{page}:{page_size}:{movement_type}"
    f":{start_date}:{end_date}"
)
```

Without the dates appended, `stock:movements:1:10:RECEIVE` would be the key for both "all RECEIVE movements" *and* "RECEIVE movements in January" — so a date-filtered request would be served the unfiltered cached result.

This is the mirror image of the Phase 10.4 bug. There, a write forgot to **invalidate** a cache. Here, a read would have forgotten to **distinguish** between two different questions.

```text
Every parameter that changes the answer must be part of the key.
```

### The access-model change worth noticing

Date filtering used to live only on `/reports/movement-history`, which is `get_current_admin`. Moving it to `/stock/movements`, which is `get_current_user`, **gave every authenticated user a capability that had been admin-only**.

That was judged correct — movement history was already fully readable by any user, so date-filtering it reveals nothing new. But it is an access change, not a refactor, and worth deciding deliberately rather than discovering later.

### What Reports kept

```ts
export const getStockSummary = async (): Promise<StockSummaryResponse>
export const getTopProducts = async (): Promise<TopProductsResponse>
```

Neither takes parameters. Stock summary is a snapshot of what you hold *now*; top products is an all-time aggregate. Neither can be narrowed by date even in principle — so the date pickers came off Reports entirely.

A control that changes nothing when clicked is worse than no control: it lies about what the page can do.

---

## Part 5 — The Timezone Bug

### The symptom

Filter set to 18/07 → 21/07. Rows dated 22/07 still on screen. The filter looked broken.

### Proving where it wasn't

```bash
curl ".../stock/movements?start_date=2026-07-18&end_date=2026-07-21"
total: 24
newest returned: 2026-07-21T23:03:52Z
```

The backend obeyed perfectly — nothing past the 21st came back. So the bug was downstream of the API.

### The cause

```tsx
new Date('2026-07-21T23:03:52Z').toLocaleDateString('en-GB')
```

The `Z` means UTC. `toLocaleDateString` renders in the **viewer's** timezone — Dublin, UTC+1 in summer. So 23:03 on the 21st displays as **00:03 on the 22nd**.

```text
Filtering happened in UTC.
Display happened in local time.
At every day boundary, they disagreed by an hour.
```

The row was genuinely inside the range. Only the label was outside it.

### The decision

Two directions, and they trade against each other:

```text
Display in UTC        -> filter and display agree
                      -> but a movement made at 00:30 local shows as the previous day

Filter in local time  -> "the 18th" means the user's 18th
                      -> but the backend must be told which timezone that is
```

Local display was chosen, on the grounds that people think in their own calendar. Seeing a stock count you did at 00:30 filed under yesterday is confusing no matter how correct UTC is.

### The implementation

The backend stopped taking `date` and started taking `datetime`:

```python
start_date: datetime | None = Query(default=None)
end_date: datetime | None = Query(default=None)
```

and the browser — the only party that knows the timezone — picks the boundaries:

```ts
const startInstant = startDate
  ? new Date(`${startDate}T00:00:00`).toISOString()
  : undefined
const endInstant = endDate
  ? new Date(`${endDate}T23:59:59.999`).toISOString()
  : undefined
```

**The trick is the missing `Z`:**

```js
new Date('2026-07-18T00:00:00Z')   // has Z  -> parsed as UTC
new Date('2026-07-18T00:00:00')    // no Z   -> parsed as LOCAL
```

So `${startDate}T00:00:00` means "midnight on the 18th where the user is sitting," and `.toISOString()` converts that instant to UTC — `2026-07-17T23:00:00.000Z` in Dublin. The user's midnight, expressed in the database's language.

This lives in `api/stock.ts`, not the page. `MovementsPage` still passes plain `YYYY-MM-DD` strings — wire format is the API layer's job, same as the `/api/v1` prefix and snake_case parameter names.

### Why `datetime.combine` disappeared

The old code did this:

```python
datetime.combine(start_date, datetime.min.time())   # 00:00:00
datetime.combine(end_date, datetime.max.time())     # 23:59:59.999999
```

A `date` is a **box** covering 24 hours; `created_at` is a **point**. Comparing them requires choosing which edge of the box you mean. `combine` made that choice explicit.

Without it, Postgres coerces a bare date to midnight, so `created_at <= 2026-07-21` silently drops the entire 21st — the classic off-by-one-day bug, failing quietly.

Once the frontend sends a precise instant, the edge has already been chosen by the party that knew the timezone. There is no box left to pick an edge from.

### The sharp edge left behind

Bare dates still parse, but now mean *start of that day*:

```text
?start_date=2026-07-18&end_date=2026-07-21   ->  total: 0
```

That same request returned 24 an hour earlier. The frontend never sends bare dates, but a Swagger user would hit it. Known and accepted rather than discovered later.

---

## Part 6 — The Verification That Verified Nothing

### How it surfaced

VS Code reported a real error:

```text
MovementsPage.tsx(42,9): Expected 0-3 arguments, but got 5.
```

while the command being used to confirm the work reported success. One of them was lying.

### The cause

```json
// frontend/tsconfig.json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

This is a **solution-style** config — a table of contents, not a config. The real settings live in the two referenced files.

```text
tsc --noEmit   reads tsconfig.json, sees files: [], checks ZERO files, exits 0
tsc -b         "build mode" — FOLLOWS the references and checks both projects
```

`--noEmit` had been reporting success by checking nothing at all, across multiple sessions.

A second, smaller mistake compounded it: piping `tsc` output through `head` and then reading `$?` reports **head's** exit code, which is always 0.

### What it had been hiding

```text
src/main.tsx(3,8): Cannot find module or type declarations for
                   side-effect import of './index.css'.
```

`src/vite-env.d.ts` was missing — never created by the original scaffold. Since `npm run build` is `tsc -b && vite build`, and `tsc -b` failed, **the production build had never succeeded once** in the project's history.

The fix is one line:

```ts
/// <reference types="vite/client" />
```

TypeScript only trusts imports it has a type for. A `.css` file isn't code it understands, so it refuses rather than guessing. Vite ships the declarations; that triple-slash directive is what loads them.

### The three levels of confidence

```text
VS Code squiggles   only files you have OPEN
tsc --noEmit        nothing, in this repo
npm run build       every file + the real production bundle
```

---

## Part 7 — Indexing `created_at`

Every movements query already ordered by `created_at DESC`, and now filters on it too. The column had no index.

```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    nullable=False,
    index=True,
)
```

### What an index actually costs

An index is a **second structure** — a sorted list of every value with a pointer back to its row. Reads get to jump into it like a dictionary instead of scanning the table. Writes pay for it: every `INSERT` now writes twice, once to the table and once into the index at the correct sorted position.

For `stock_movements` that write cost is real — a row per stock adjustment, and one per line item on every order create and cancel.

**It's worth it here for a specific reason:** timestamps only ever increase. Every new value is later than everything already indexed, so it always appends to the end of the sorted structure — never squeezed into the middle, no page splits, no shuffling. Append-only plus monotonically increasing is close to the ideal case for a B-tree index.

### Why the rows being "already in order" isn't enough

The table's physical order genuinely *does* roughly match `created_at`, since rows are inserted chronologically. But Postgres cannot assume that: `UPDATE` writes new row versions elsewhere, deleted rows leave gaps that later inserts reuse, `VACUUM` reorganises pages, and nothing prevents a backdated insert.

```text
incidentally ordered   looks identical from outside
guaranteed ordered     is what lets the planner take a shortcut
```

The index buys a guarantee, not a copy of good luck.

### Model and migration are one change

```python
index=True                    # declares intent, changes no database
alembic revision --autogenerate  # writes the CREATE INDEX
alembic upgrade head             # actually creates it
```

They must be committed together. The model alone leaves anyone who pulls with code describing an index their database doesn't have.

**Reviewing an autogenerated migration** — three checks: does it do *only* what you asked, is `down_revision` the previous head, is `downgrade()` a true inverse? Autogenerate is a first draft, and gets confused by enums and server defaults especially.

---

## What Changed in the Project

```text
backend/
  app/services/stock_service.py   -> date filters + dates in cache key
  app/routers/stock.py            -> start_date/end_date as datetime
  app/models/stock_movement.py    -> index=True on created_at
  alembic/versions/64d1d64...     -> CREATE INDEX migration

frontend/src/
  api/reports.ts                  -> NEW: four report endpoints typed
  pages/DashboardPage.tsx         -> NEW: KPI tiles + low-stock table
  pages/ReportsPage.tsx           -> NEW: stock summary + top products
  api/stock.ts                    -> local date -> UTC instant conversion
  pages/MovementsPage.tsx         -> date range filter, [color-scheme:dark]
  components/layout/AppHeader.tsx -> role-filtered tabs
  components/layout/ProtectedRoute.tsx -> fallback /dashboard -> /products
  App.tsx                         -> nested adminOnly route block
  vite-env.d.ts                   -> NEW: fixed a build broken since June
```

---

## Technical Lessons

### 1. A wireframe is a proposal, not a specification

Including one you wrote yourself. Challenge it before the code exists — that's the cheapest moment.

### 2. A guard's fallback must be somewhere the rejected user can go

Otherwise it doesn't terminate.

### 3. Every parameter that changes the answer belongs in the cache key

Forgetting to *distinguish* is the same bug class as forgetting to *invalidate*.

### 4. Moving a filter between endpoints can move an access boundary

Notice it deliberately rather than discovering it later.

### 5. A control that changes nothing is worse than no control

It lies about what the page can do.

### 6. UTC storage plus local display disagree at every day boundary

Decide which one wins, then make the other follow. Don't leave them split.

### 7. `new Date('...T00:00:00')` without `Z` parses as local — deliberately useful

It is how the browser converts a user's calendar day into an instant.

### 8. Verify your verification

`tsc --noEmit` passed on a broken build for months. Check that your check can actually fail.

### 9. An index buys a guarantee, not a copy of luck

"Probably in order" is not something a query planner can act on.

### 10. Model change and migration are one commit

Split them and the schema drifts from the code describing it.

---

## Final State After This Part

- `/dashboard` — admin-only, four KPI tiles, full low-stock table with computed deficit;
- `/reports` — admin-only, stock summary with total inventory value, top products;
- role-filtered nav; `ProtectedRoute.adminOnly` in real use with a terminating fallback;
- `/movements` — one table, type *and* date filters, filtering in the user's timezone;
- `stock_movements.created_at` indexed, migration applied and verified in Postgres;
- a production build that succeeds for the first time in the project's history;
- 88/88 backend tests passing.

### Known gaps, deliberately left

```text
top-products counts cancelled orders   -> UI captions it rather than misreporting
OrderStatus.FULFILLED                  -> in the enum, no endpoint sets it
GET /reports/movement-history          -> zero callers now
bare dates on /stock/movements         -> mean start-of-day; frontend never sends them
```

---

## Recap in One Diagram

```text
PHASE 10.6

AppHeader (tabs filtered by is_admin)
  │
  ├─ Dashboard (admin) ──> Promise.all
  │                          stock-summary  -> total products, inventory value
  │                          low-stock      -> the table + count
  │                          movement-history(7d, page_size=1) -> total only
  │                        low-stock row ──> /products/:id/stock
  │
  ├─ Reports (admin) ────> stock summary (no params — a snapshot)
  │                        top products  (no params — all-time)
  │
  └─ Movements (any user)
        [All|Receive|Ship|Adjust]  instant — one click, one complete value
        [start][end][Apply]        deferred — two values, only meaningful together
                    │
                    ├─ browser: `${date}T00:00:00` (no Z = local) -> toISOString()
                    ↓
        GET /stock/movements?movement_type=&start_date=<instant>&end_date=<instant>
                    ↓
        cache key includes EVERY filter
                    ↓
        WHERE created_at >= start AND <= end   ← now indexed (btree)
                    ↓
        rendered with toLocaleDateString -> matches the range the user picked
```