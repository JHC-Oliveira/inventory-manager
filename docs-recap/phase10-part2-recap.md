# Phase 10.2 Recap — Product Dashboard & CRUD UI

## What Is Covered

This is **Part 2** of Phase 10. Part 1 got a user logged in. This part gives them something to do once they are inside: a dashboard that lists products and lets an admin create, edit, and delete them.

The work had four connected pieces:

1. a typed API module for products;
2. loading and displaying the product list;
3. one form component that handles both create and edit;
4. role-aware UI — the same page renders differently for an admin and a normal user.

```text
PART 1
Types and API functions for products

PART 2
Fetch and render the list

PART 3
One form, two modes

PART 4
Same page, different capabilities per role
```

This is the first part of the project where the frontend has real application logic, not just authentication plumbing.

---

## Big Picture

```text
Before
  logged-in users saw an empty dashboard
  product CRUD existed only in Swagger

After
  dashboard lists paginated products
  admins can create, edit, and delete inline
  non-admins see the same data with no write controls
  loading states, empty states, and error states all handled
```

---

## Why This Part Matters

Almost every real internal tool is this exact shape: a list of records, a form to change them, and permissions deciding who sees which buttons. Getting this pattern right once means every later page (stock, movements, orders) is a variation rather than a new problem.

```text
Phase 10.1  -> can a user get in?
Phase 10.2  -> can they do the core job once inside?
```

---

## Part 1 — The Products API Module

### The pattern established here

`src/api/products.ts` sets the template that every later API module (`stock.ts`, `orders.ts`) copies:

```text
1. export the response types
2. export the payload types
3. export one thin async function per endpoint
4. never call axios directly from a component
```

```ts
export const getProducts = async (page = 1, pageSize = 12): Promise<ProductsResponse> => {
  const response = await client.get('/products', {
    params: { page, page_size: pageSize },
  })
  return response.data as ProductsResponse
}
```

### Why a separate module instead of calling axios in the page

```text
axios in components
  -> URL strings scattered across files
  -> response shapes re-typed at every call site
  -> changing an endpoint means hunting through pages

api/ module
  -> one place per resource
  -> one type definition consumed everywhere
  -> page components stay about rendering, not HTTP
```

This mirrors the backend's own rule — routers handle HTTP, services own logic. Here, `api/*.ts` handles HTTP and pages own the UI.

### `price: string`, not `number`

A detail that looks like a mistake but is not:

```ts
export type Product = {
  price: string
  quantity: number
  ...
}
```

`price` is `Numeric(10, 2)` in PostgreSQL and `Decimal` in Pydantic. Pydantic serialises `Decimal` to a **JSON string**, not a number, deliberately — JavaScript numbers are IEEE-754 doubles and cannot represent every decimal exactly. Serialising as a string means the exact value crosses the wire intact, and the frontend decides when to convert:

```tsx
€{Number(price).toFixed(2)}
```

`quantity` is a plain integer, so it stays a `number`.

```text
money      -> Decimal -> JSON string -> Number() only for display
counts     -> int     -> JSON number -> used directly
```

---

## Part 2 — Loading the List

### The three states every data view needs

The dashboard handles all three explicitly rather than only the happy path:

```text
loading      -> <ProductsSkeleton />
error        -> red panel with getErrorMessage(...)
empty        -> "No products yet."
loaded       -> the list
```

### Why a skeleton and not a spinner

`ProductsSkeleton` renders grey pulsing blocks in the shape of the content that is about to appear.

```text
Spinner
  -> layout jumps when content arrives
  -> no sense of how much is coming

Skeleton
  -> page height stays stable
  -> the shape of the answer is visible immediately
```

### The load function shape

```tsx
const loadProducts = async (targetPage: number) => {
  try {
    setLoading(true)
    setPageError('')
    const data = await getProducts(targetPage, 12)
    setProducts(data.items)
    setTotal(data.total)
    setTotalPages(data.total_pages)
    setPage(data.page)
  } catch (err) {
    setPageError(getErrorMessage(err, 'Failed to load products.'))
  } finally {
    setLoading(false)
  }
}
```

Two habits worth naming:

- `setPageError('')` **before** the request, so a previous failure does not linger next to fresh data;
- `setLoading(false)` in `finally`, so a failed request cannot leave the page stuck on the skeleton forever.

### Page state comes from the server, not the click

`setPage(data.page)` uses the value the backend returned rather than the value that was requested. If the two ever disagree — for example, requesting page 5 of a list that shrank to 3 pages — the UI follows reality instead of its own optimistic guess.

---

## Part 3 — One Form, Two Modes

### The problem

Creating a product and editing a product need the same six fields, the same validation, and the same layout. Two separate components would mean every future field change has to be made twice, and would eventually drift.

### The solution

`ProductForm` takes a `mode` prop:

```tsx
type Props = {
  mode: 'create' | 'edit'
  initialData?: Product | null
  onSubmit: (data: CreateProductPayload) => Promise<void>
  onCancel: () => void
  loading: boolean
  externalError?: string
}
```

`mode` controls the heading, the button label, and how the fields are seeded:

```tsx
useEffect(() => {
  if (mode === 'edit' && initialData) {
    setForm({ ...prefilled from initialData })
    return
  }
  setForm({ ...all empty })
}, [mode, initialData])
```

The effect depends on `[mode, initialData]`, so switching from editing product A to editing product B re-seeds the fields — without that dependency the form would keep showing A's values.

### Why the form does not call the API itself

`ProductForm` never imports `createProduct` or `updateProduct`. It calls `onSubmit(data)` and lets the page decide what that means.

```text
Form owns:   field state, validation, layout
Page owns:   which API call, what to do after, reloading the list
```

That is what makes the same component reusable in two places, and later lets the page render it either as a top panel (create) or inside an expanded table row (edit) without the form knowing the difference.

### Two error channels

```tsx
{(error || externalError) && ( ... )}
```

- `error` is **local validation** — "Price must be a positive number", decided before any request;
- `externalError` is **server rejection** — passed down from the page, e.g. a 409 for a duplicate SKU.

Both render in the same place so the user never has to look in two spots, but they come from genuinely different sources.

### Client validation duplicates the server on purpose

The form checks price is positive and quantity is not negative — rules the backend also enforces. That duplication is intentional and one-directional:

```text
Frontend validation  -> fast, specific feedback, no round trip
Backend validation   -> the rule that actually protects the data
```

The frontend copy can be removed without creating a security hole. The backend copy cannot.

---

## Part 4 — Role-Aware UI

### One page, two experiences

Every write control is wrapped in the same check:

```tsx
{user?.is_admin && (
  <Button onClick={openCreateForm}>Add product</Button>
)}
```

and passed down to the card:

```tsx
<ProductCard canManage={!!user?.is_admin} ... />
```

```text
Admin      -> Add product, Edit, Delete, Manage stock
Non-admin  -> the same list, read-only
```

### Why `!!user?.is_admin`

`user` may be `null` before the store is populated. `user?.is_admin` is therefore `boolean | undefined`, while the prop is typed `boolean`. The double negation converts `undefined` to `false` — TypeScript catching a real "not loaded yet" state rather than being pedantic.

### This is presentation, not permission

Worth restating from Part 1: hiding the Delete button does not stop anyone deleting a product. `get_current_admin` on `DELETE /products/{id}` does. The frontend check exists so a non-admin is not shown a button that would only ever return 403.

```text
UI gating       -> don't offer what will be refused
Backend gating  -> refuse it regardless of what the UI offered
```

### Confirming destructive actions

```tsx
const confirmed = window.confirm(
  `Delete "${product.name}"? This action cannot be undone.`
)
if (!confirmed) return
```

Native `window.confirm` was chosen over building a modal component — the project had no dialog component yet, and one confirmation did not justify introducing one. Naming the specific product in the message matters: a generic "Are you sure?" is easy to click through on the wrong row.

---

## What Changed in the Project

```text
frontend/src/
  api/products.ts                        -> types + getProducts/create/update/delete
  pages/DashboardPage.tsx                -> list, states, form orchestration
  components/products/ProductCard.tsx    -> one product, role-aware actions
  components/products/ProductForm.tsx    -> create/edit in one component
  components/products/ProductsSkeleton.tsx -> loading placeholder
```

No backend changes were needed in this part — Phase 3's product endpoints were already complete and correctly gated.

---

## Technical Lessons

### 1. Keep HTTP out of components

`api/*.ts` per resource keeps URLs and response types in one place, and keeps pages about rendering.

### 2. Money crosses the wire as a string

`Decimal` → JSON string is deliberate. Convert with `Number()` only at the point of display.

### 3. Handle four states, not one

Loading, error, empty, and loaded are all real. Only handling "loaded" is what makes a UI feel broken.

### 4. `finally` is where loading flags get cleared

A `catch` that forgets to reset `loading` leaves the page permanently stuck.

### 5. One component, a `mode` prop, and callbacks instead of API calls

That combination is what makes `ProductForm` reusable in two different layouts later without modification.

### 6. Trust the server's echo of pagination state

Using `data.page` rather than the requested page keeps the UI honest when the data changed underneath.

---

## Final State After This Part

- a typed `api/products.ts` module wrapping all five product endpoints;
- a dashboard listing paginated products with skeleton, empty, and error states;
- `ProductForm` handling create and edit through one `mode` prop;
- `ProductCard` rendering a product with role-aware action buttons;
- admin-only write controls, with the backend still doing the real enforcement;
- confirmation before deletion, naming the specific product.

Known gaps at this point, both fixed in Part 4: the list was **hardcoded to page 1** with no pagination controls, and the card grid grew unwieldy with many products.

---

## Recap in One Diagram

```text
PHASE 10.2

DashboardPage mounts
  ↓
loadProducts(1) ──> api/products.ts ──> GET /api/v1/products?page=1
  ↓                                        (Bearer token via interceptor)
setProducts / setTotal / setTotalPages
  ↓
loading? ──> ProductsSkeleton
error?   ──> red panel (getErrorMessage)
empty?   ──> "No products yet."
  ↓
ProductCard per product
  ↓ canManage (user.is_admin)
  ├── Edit   ──> ProductForm mode="edit"   ──> updateProduct ──> reload
  └── Delete ──> window.confirm            ──> deleteProduct ──> reload

Add product (admin only) ──> ProductForm mode="create" ──> createProduct ──> reload
```