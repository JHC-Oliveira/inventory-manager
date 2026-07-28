# Phase 10.1 Recap — Frontend Foundation & Authentication UI

## What Is Covered

Phase 10 is the React frontend. It is large enough that it is split into five recap parts. This is **Part 1**: standing up the frontend at all, and getting a user logged in.

The work had five connected pieces:

1. scaffold a React + TypeScript + Vite app and put it in Docker alongside the API;
2. build one shared axios client that talks to the versioned backend;
3. hold auth state in Zustand and gate routes behind it;
4. build the Login and Register pages;
5. fix the contract mismatch between what the backend returned and what the frontend expected.

```text
PART 1
A React app that exists and can reach the API

PART 2
One HTTP client, one place that knows about tokens

PART 3
Auth state in memory, routes that respect it

PART 4
Login and Register screens

PART 5
Make backend and frontend agree on the response shape
```

Phases 1–9 built an API. Nothing consumed it except Swagger and pytest. This part gives it a real client.

---

## Big Picture

```text
Before
  FastAPI backend under /api/v1
  -> tested with pytest and Swagger only
  -> no browser client
  -> no session concept outside JWTs in curl

After
  React app on :5173 in its own container
  -> axios client injecting Bearer tokens automatically
  -> Zustand store holding the session
  -> protected routes that redirect to /login
  -> working Login and Register screens
```

The important shift is that the backend stopped being the whole system and became **one half of a contract**. Most of the bugs in this part came from the two halves disagreeing.

---

## Why This Phase Matters

```text
Phases 1–9
  "the API returns the right JSON"

Phase 10.1
  "a real client can hold a session and act on that JSON"
```

That matters because in interviews the follow-up question to "you built an API" is almost always "how does the frontend authenticate against it?" Answering that requires knowing where the token lives, who attaches it to requests, and what happens on refresh — all decided here.

---

## Part 1 — Scaffolding and Docker

### The problem

The backend already ran in Docker Compose with PostgreSQL, Redis, and RabbitMQ. Adding a frontend that runs on the host with `npm run dev` would mean two different ways of running the project, and a CORS/origin problem between `localhost:5173` and `localhost:8000`.

### The solution

The frontend became a fourth service in the same Compose network, and Vite's dev server proxies API calls to the backend container.

```ts
// vite.config.ts
server: {
  host: '0.0.0.0',              // required for Docker — not 127.0.0.1
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://api:8000', // 'api' is the Docker service name
      changeOrigin: true,
    },
  },
}
```

### Why `host: '0.0.0.0'` is required

By default Vite binds to `127.0.0.1`, which inside a container means "only reachable from inside this same container." The port mapping in Compose would forward to a port nothing was listening on from the outside.

```text
host: 127.0.0.1  -> reachable only inside the container -> port mapping appears broken
host: 0.0.0.0    -> reachable on every interface        -> port mapping works
```

### Why the proxy matters more than it looks

The proxy is not a convenience. It is what makes the browser treat the API as **same-origin**.

```text
Without proxy
browser at localhost:5173 calls localhost:8000
  -> different origin
  -> CORS preflight on every request
  -> cookies need cross-site configuration

With proxy
browser at localhost:5173 calls localhost:5173/api/...
  -> same origin
  -> no CORS complexity
  -> cookies "just work"
```

That decision pays off directly in Part 3, where the refresh token moves into a cookie.

### Stack chosen

```text
React 19 + TypeScript   -> typed components
Vite                    -> dev server + build
Tailwind v4             -> styling
shadcn / radix          -> accessible base components
axios                   -> HTTP
Zustand                 -> auth state
React Router            -> routing
```

---

## Part 2 — The Shared HTTP Client

### The problem

Every API call needs the same three things: the `/api/v1` prefix, the `Authorization` header, and cookie credentials. Repeating that in every function is how a codebase ends up with one endpoint that silently forgets the token.

### The solution

One axios instance in `src/api/client.ts`, and a **request interceptor** that attaches the token on the way out.

```ts
const client = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
})

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

### Why an interceptor and not a helper function

An interceptor is middleware for outgoing requests — the same idea as the request-logging middleware from Phase 9, pointed the other direction.

```text
Helper function
  -> every call site must remember to use it
  -> one forgotten call = one unauthenticated request

Interceptor
  -> applies to every request through this client automatically
  -> impossible to forget
```

### Why `useAuthStore.getState()` and not the hook

`useAuthStore(...)` is a React hook and can only be called inside a component render. The interceptor runs outside React entirely, whenever a request fires. `getState()` reads the same store imperatively.

```text
useAuthStore(selector)      -> inside components, re-renders on change
useAuthStore.getState()     -> anywhere, reads current value once
```

Reading it *inside* the interceptor (rather than capturing it once at module load) matters: the token changes on login, and the interceptor must see the current one, not the `null` that existed when the file was first imported.

### Why `baseURL: '/api/v1'`

Phase 9 versioned the API. The frontend encodes that prefix in exactly one place, so every call site writes `client.get('/products')` and never repeats the version.

---

## Part 3 — Auth State and Protected Routes

### The store

```ts
export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  logout: () => set({ accessToken: null, user: null }),
}))
```

Zustand was chosen over Context because it can be read from outside React (the interceptor above needs exactly that) and does not re-render the whole tree on every change.

### Why the token lives in memory, not localStorage

This is a deliberate security decision, revisited in depth in Part 3 of this phase.

```text
localStorage
  -> survives refresh
  -> readable by any JavaScript on the page
  -> an XSS payload can steal the token

memory (Zustand)
  -> lost on refresh (fixed later with a cookie)
  -> not reachable by injected scripts
```

### The route guard

```tsx
export default function ProtectedRoute({ adminOnly = false }: Props) {
  const { accessToken, user } = useAuthStore()

  if (!accessToken) return <Navigate to="/login" replace />
  if (adminOnly && !user?.is_admin) return <Navigate to="/dashboard" replace />

  return <Outlet />
}
```

### Why `<Outlet />` instead of wrapping children

`ProtectedRoute` is used as a **layout route** — one guard wrapping many routes, rather than one guard repeated per route.

```tsx
<Route element={<ProtectedRoute />}>
  <Route path="/products" element={<ProductsPage />} />
  <Route path="/movements" element={<MovementsPage />} />
  <Route path="/orders" element={<OrdersPage />} />
</Route>
```

`<Outlet />` is the placeholder React Router fills with whichever child route matched. Adding a new protected page means adding one line inside the block — the guard is never re-stated and can never be forgotten on a new route.

### Why `replace`

`<Navigate to="/login" replace />` replaces the current history entry instead of pushing a new one. Without it, pressing Back after being redirected sends the user to the protected page again, which bounces them forward again — a loop.

### This guard is UX, not security

An important framing: `ProtectedRoute` stops a user *seeing* a page. It does not protect data. Anyone can edit the store in devtools and render `/products`. What actually protects the data is `get_current_user` / `get_current_admin` on the backend, which the page's API calls will still fail against.

```text
Frontend guard  -> convenience, avoids showing a broken empty page
Backend guard   -> the real access control
```

---

## Part 4 — Login and Register Pages

Both pages are deliberately plain: local `useState` for fields, one submit handler, one error string. No form library, because there was nothing yet to justify one.

```tsx
const data = await login({ email, password })
setAuth(data.access_token, data.user)
navigate('/dashboard')
```

### Register does not log you in

`RegisterPage` calls `register(...)` then navigates to `/login` rather than storing the returned token. This is a UX choice: it confirms the account works by making the user sign in once, and keeps the "you are logged in" path in one place.

### Surfacing real validation errors

The backend enforces password rules in `UserRegister`:

```text
at least 8 characters
at least one uppercase letter
at least one number
full name at least 2 characters
```

Rather than letting a user discover these by trial and error, `RegisterPage` lists them under the password field, and the submitted error is rendered with `whitespace-pre-line` so multi-line backend messages keep their line breaks.

### The shared error reader

```ts
export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const backendMessage = error.response?.data?.message
    if (typeof backendMessage === 'string' && backendMessage.trim()) {
      return backendMessage
    }
  }
  return fallback
}
```

This is the frontend half of Phase 9's error envelope. Because every backend failure returns `{ error, message, status_code }`, one function can read `message` from any failed request in the whole app.

```text
Phase 9 decision:  one error shape everywhere
Phase 10 payoff:   one error reader everywhere
```

The `fallback` argument exists for failures that never reached the backend — a dropped connection has no response body to read.

---

## Part 5 — The Contract Mismatch

### The problem

The first working version of the login flow revealed that the two halves disagreed about the response shape. The backend returned tokens; the frontend also needed to know **who** had just logged in — `full_name` for the header, `is_admin` to decide which buttons exist.

Without the user object, the frontend would have had to either decode the JWT client-side to read `is_admin` (fragile, and encourages treating unverified claims as trusted) or make a second request immediately after login.

### The fix

`TokenResponse` gained the user:

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
```

`UserResponse` already existed and already excluded `hashed_password`, so no new leak risk was introduced — the safe shape was reused rather than a new one invented.

### The lesson

```text
Building API-first, then a client
  -> the contract looks complete until something consumes it
  -> "returns a token" is not the same as "returns what a session needs"
```

The tests had to be updated in the same pass (`e3718ef`), because the response shape they asserted on had changed. That cost is normal and is the signal that the contract genuinely moved.

---

## What Changed in the Project

```text
frontend/
  Dockerfile, vite.config.ts        -> containerised dev server + API proxy
  src/api/client.ts                 -> axios instance + Bearer interceptor
  src/api/auth.ts                   -> login / register / logout / refresh
  src/store/authStore.ts            -> Zustand auth state
  src/components/layout/
    ProtectedRoute.tsx              -> layout-route auth guard
  src/pages/LoginPage.tsx           -> sign-in screen
  src/pages/RegisterPage.tsx        -> sign-up screen
  src/lib/errors.ts                 -> getErrorMessage helper

backend/
  app/schemas/user.py               -> TokenResponse now includes user
  tests/                            -> updated for the new response shape
```

---

## Technical Lessons

### 1. A proxy turns two origins into one

Routing `/api` through the Vite dev server removes an entire class of CORS and cookie problems before they start.

### 2. Cross-cutting request concerns belong in an interceptor

Same principle as backend middleware: if every request needs it, do not make every call site remember it.

### 3. Read state at call time, not at import time

`useAuthStore.getState()` inside the interceptor sees the current token. Capturing it at module scope would freeze the `null` it started with.

### 4. Frontend route guards are UX; backend dependencies are security

Both are needed, but only one of them actually protects data.

### 5. One error envelope enables one error reader

The Phase 9 decision to standardise `{ error, message, status_code }` is what makes a nine-line `getErrorMessage` sufficient for the entire app.

### 6. A contract is only proven once something consumes it

The missing `user` field was invisible while the only clients were pytest and Swagger.

---

## Final State After This Part

- a React 19 + TypeScript + Vite app running in Docker on port 5173;
- Vite proxying `/api` to the backend container, keeping the browser same-origin;
- one axios client that injects the Bearer token on every request;
- auth state in a Zustand store, readable from inside and outside React;
- a reusable `ProtectedRoute` layout guard with an admin-only mode;
- working Login and Register pages with real backend validation surfaced;
- one shared `getErrorMessage` helper built on the Phase 9 error envelope.

Known gap at this point, fixed in Part 3: **a page refresh logs the user out**, because the store is memory-only.

---

## Recap in One Diagram

```text
PHASE 10.1

browser (localhost:5173)
  ↓
Vite dev server  ── /api/* ──>  api:8000 (same-origin to the browser)
  ↓
React app
  ↓
ProtectedRoute — accessToken in Zustand?
  ↓ no ──> /login ──> POST /auth/login ──> setAuth(token, user)
  ↓ yes
page renders
  ↓
axios client + interceptor
  ↓ Authorization: Bearer <token>
FastAPI /api/v1/... (get_current_user)
  ↓ on failure
{ error, message, status_code } ──> getErrorMessage ──> shown to user
```