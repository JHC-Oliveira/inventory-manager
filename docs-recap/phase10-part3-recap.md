# Phase 10.3 Recap — Persisting Login with httpOnly Cookies

## What Is Covered

This is **Part 3** of Phase 10, and it is the security-heavy one. Parts 1 and 2 left a real bug: **refreshing the page logged the user out.** Fixing it properly meant deciding where a session token is allowed to live in a browser, and moving the refresh token out of JavaScript's reach entirely.

The work had five connected pieces:

1. understand why the session was lost, and why the obvious fix is the wrong one;
2. move the refresh token into an httpOnly cookie on the backend;
3. remove the refresh token from the frontend completely;
4. silently restore the session on app boot;
5. fix the test suite, including a fake Redis that could not actually remember anything.

```text
PART 1
Why a refresh wipes the session — and why localStorage is not the answer

PART 2
Backend: set, read, and clear an httpOnly cookie

PART 3
Frontend: stop holding the refresh token at all

PART 4
Rehydrate the session before the first render

PART 5
Tests that prove the cookie flow works end to end
```

---

## Big Picture

```text
Before
  refresh token returned in the JSON login response
  stored in the Zustand store alongside the access token
  page refresh -> store resets to null -> ProtectedRoute -> /login
  any XSS payload could read both tokens

After
  refresh token set as an httpOnly cookie, never in the JSON body
  JavaScript literally cannot read it — not even our own code
  access token still in memory, still sent as Bearer
  app boot silently calls /auth/refresh to restore the session
  page refresh keeps the user logged in
```

---

## Why This Part Matters

This is the part of the project with a genuine threat model behind it, and it is the one most likely to come up in an interview.

```text
"Where do you store the JWT?"
  -> localStorage        = the answer that fails the follow-up question
  -> httpOnly cookie     = the answer that leads to a real conversation
```

The interesting part is not that cookies were chosen. It is *which* token went in the cookie and why the other one deliberately did not.

---

## Part 1 — The Bug and the Tempting Wrong Fix

### What was happening

`ProtectedRoute` redirects whenever `accessToken` is missing. The Zustand store is plain memory with no persistence, so a hard refresh resets it to `null` and the guard fires — even though the session was still perfectly valid on the server.

```text
F5 pressed
  -> JS heap discarded
  -> Zustand store re-initialises with accessToken: null
  -> ProtectedRoute sees null
  -> redirect to /login

The server never knew anything happened.
```

This was not a logout bug. There was simply **no rehydration step on boot**.

### The tempting fix, and why it was rejected

The one-line fix is to persist the store to `localStorage`. It works, and it is what most tutorials do. It was rejected deliberately.

Think of the access token as a wristband at a venue. `localStorage` is like writing your wristband number on a whiteboard in the lobby — convenient for you, readable by anyone who walks past. Any JavaScript running on the page can read `localStorage`, which means **any successful XSS becomes a full session theft**: an injected script reads the token and sends it to an attacker, who can then act as that user from anywhere.

```text
localStorage / sessionStorage
  -> readable by document.cookie-level JS
  -> XSS = token exfiltration

httpOnly cookie
  -> the browser attaches it to requests automatically
  -> JS cannot read it, including our own code
  -> XSS can still act as the user in the page, but cannot steal the session
```

An httpOnly cookie does not make XSS harmless — a script can still fire requests from inside the page — but it stops the attacker from walking away with a durable credential.

---

## Part 2 — The Split Decision: Which Token Goes in the Cookie

This is the key design choice of this part, and the reason the change stayed small.

```text
Refresh token  -> moves into an httpOnly cookie
Access token   -> stays exactly as it was, in memory, sent as Bearer
```

### Why not put both in cookies

Because the moment the browser starts attaching credentials **automatically** to requests, CSRF becomes a problem. A cookie is sent by the browser on any request to that origin — including one triggered by a malicious page the user is visiting in another tab.

An `Authorization: Bearer` header is different: it only exists because our JavaScript explicitly put it there. A third-party site cannot make the browser add it.

```text
Cookie auth   -> sent automatically -> vulnerable to CSRF -> needs CSRF tokens
Bearer header -> sent only by our code -> immune to CSRF by construction
```

Keeping the access token in a header means **the entire product/stock/order API needs no CSRF defence at all**, and `get_current_user` / `oauth2_scheme` in `dependencies/auth.py` were not touched.

### Scoping the cookie's blast radius

```python
response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,                       # JS cannot read it
    secure=settings.cookie_secure,       # HTTPS-only in production
    samesite="lax",                      # not sent on cross-site requests
    path=f"{settings.api_prefix}/auth",  # only sent to /api/v1/auth/*
    max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
)
```

Each flag is doing a specific job:

```text
httponly=True   -> document.cookie cannot see it
secure          -> refuses to travel over plain HTTP (production only)
samesite="lax"  -> another site cannot trigger a request that carries it
path=/api/v1/auth -> the browser only attaches it to auth endpoints,
                     so it is not sent on every products/stock/orders call
```

The `path` scoping is the one people skip. Without it, the refresh token would ride along on every single API request — dozens of unnecessary exposures per page load.

### `cookie_secure` reuses existing config

```python
@property
def cookie_secure(self) -> bool:
    return self.app_env == "production"
```

No new setting was introduced. `secure=True` requires HTTPS, which local development does not have — so the flag follows the environment automatically instead of being a manual toggle someone forgets to flip.

### The refresh token leaves the JSON body

This is the actual fix, and it is easy to get wrong by adding the cookie while leaving the body untouched:

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    # refresh_token: str   <- removed
```

If the token is still in the response body, JavaScript can still read it, and the whole exercise was pointless.

### Reading it back on refresh

```python
token = request.cookies.get("refresh_token")
if token is None:
    raise HTTPException(401, "Not authenticated")
```

`/auth/refresh` also gained a user lookup, because the frontend needs full user info to rebuild its store on boot:

```python
class RefreshResponse(BaseModel):
    access_token: str
    user: UserResponse
    token_type: str = "bearer"
```

It re-checks `user.is_active` at this point too — so deactivating an account takes effect at the next refresh rather than lasting until the refresh token naturally expires.

### Logout has to undo two different things

```python
if token is not None:
    try:
        token_data = verify_token(token, expected_type="refresh")
        await delete_refresh_token(user_id=token_data.user_id)
    except ValueError:
        pass

response.delete_cookie(key="refresh_token", path=..., samesite="lax",
                       secure=settings.cookie_secure, httponly=True)
```

A cookie's presence in the browser and its validity on the server are two separate facts, so logout addresses both. `delete_cookie` sends a `Set-Cookie` header telling the browser to discard it — like staff cutting the wristband off your wrist. But if an attacker had already copied the raw token string, they could replay it directly against the API, bypassing the browser entirely — unless the server also considers it invalid. That is what `delete_refresh_token` does: it erases the entry from Redis, the server's own list of currently-valid wristband numbers.

Two details that are easy to get wrong:

- **the delete flags must match the set flags exactly** (`path`, `samesite`, `secure`, `httponly`) — a mismatch means the browser treats it as a different cookie and silently keeps the original;
- **a missing cookie is treated as success, not an error** — logout is idempotent, and someone who is already logged out asking to log out has got what they wanted.

---

## Part 3 — Removing the Refresh Token from the Frontend

The frontend changes were mostly deletions, which is the point: the safest way to guarantee JavaScript never leaks the refresh token is for JavaScript never to hold it.

```text
store/authStore.ts   -> refreshToken field removed entirely
api/auth.ts          -> refresh_token removed from types
                        logout() and refresh() now take no arguments
pages/LoginPage.tsx  -> setAuth(data.access_token, data.user)
DashboardPage.tsx    -> the `if (refreshToken)` guard around logout removed
```

`refresh()` and `logout()` need no arguments because the browser supplies the cookie itself — and `withCredentials: true` was already set on the axios client back in Part 1, so nothing new was needed there.

### Logout became unconditional

Previously logout only called the API if a refresh token was present in the store. With the token invisible to JS, that check is impossible — and unnecessary:

```ts
const handleLogout = async () => {
  try {
    await logoutApi()
  } catch {
    // ignore — logging out regardless
  } finally {
    clearAuth()
    navigate('/login')
  }
}
```

The `catch` is deliberately empty. If the server call fails, the local session is still cleared — a user pressing Logout must always end up logged out locally, even if the network is down.

---

## Part 4 — Silent Refresh on Boot

### The gating problem

Restoring the session requires a network round trip. If routes render during that trip, `ProtectedRoute` sees `accessToken: null` and redirects to `/login` before the answer arrives — the exact bug being fixed.

### The fix

```tsx
const [checkingAuth, setCheckingAuth] = useState(true)

useEffect(() => {
  refresh()
    .then((data) => setAuth(data.access_token, data.user))
    .catch(() => {})
    .finally(() => setCheckingAuth(false))
}, [])

if (checkingAuth) return null
```

```text
App mounts
  ↓
checkingAuth = true  -> render nothing at all
  ↓
POST /auth/refresh   (browser attaches the cookie automatically)
  ↓ success -> setAuth(token, user)
  ↓ failure -> stay logged out (empty catch — a 401 here is normal)
  ↓
checkingAuth = false -> render routes
  ↓
ProtectedRoute now sees the real answer
```

The empty `.catch(() => {})` is intentional: for a first-time visitor with no cookie, a 401 is the *expected* result, not an error worth surfacing.

### Why `return null` rather than a spinner

A blank frame for one round trip is not worth a component. Nothing reusable existed yet, and inventing a `<Spinner />` for a sub-second gap would be speculative.

### What is deliberately not solved

This restores a session across a **page refresh**. It does not silently renew an access token that expires **mid-session** — no 401-retry interceptor was built. If the 30-minute access token expires while the user is active, they are logged out, exactly as before.

```text
In scope     -> survive F5
Out of scope -> sliding sessions / automatic retry on 401
```

Naming that boundary explicitly is what stops "persist login" from quietly expanding into a much larger change.

---

## Part 5 — Fixing the Tests

### The assertions that flipped

```python
# before
assert "refresh_token" in data

# after
assert "refresh_token" not in data
assert "refresh_token" in response.cookies
```

Both halves matter. Asserting the cookie exists proves the mechanism works; asserting the body does *not* contain the token proves the vulnerability is actually closed. Only checking the first would let a regression that re-added it to the body pass silently.

### The fake Redis that could not remember

The most interesting failure in this part was in `conftest.py`. The test suite mocked Redis like this:

```python
mock_redis.get = AsyncMock(return_value=None)
```

That was fine while nothing read a value back. But the refresh flow does a genuine round trip: login **stores** the refresh token in Redis, then `/auth/refresh` **reads it back** and compares. Against a mock that always returns `None`, refresh could never succeed.

The fix was to back the mock with a real dictionary:

```python
fake_redis_store: dict[str, str] = {}

async def fake_setex(key, ttl, value):
    fake_redis_store[key] = value
    return True

async def fake_get(key):
    return fake_redis_store.get(key)

async def fake_delete(key):
    fake_redis_store.pop(key, None)
    return 1

mock_redis.setex = AsyncMock(side_effect=fake_setex)
mock_redis.get = AsyncMock(side_effect=fake_get)
mock_redis.delete = AsyncMock(side_effect=fake_delete)
```

```text
return_value  -> always the same answer, ignores what was written
side_effect   -> runs a real function, so writes affect later reads
```

The lesson generalises: **a mock that only ever returns constants can only test one-way flows.** Any store-then-read behaviour needs a stateful fake.

### The end-to-end test

One test now walks the whole flow, because this is exactly the kind of multi-step branch logic that unit assertions miss:

```text
login             -> assert cookie is set, body has no refresh_token
POST /auth/refresh (with that cookie) -> assert 200 and a user in the body
POST /auth/logout -> assert the response clears the cookie
```

---

## What Changed in the Project

```text
backend/
  app/config.py            -> cookie_secure property (reuses app_env)
  app/schemas/user.py      -> refresh_token removed from TokenResponse
                              RefreshResponse gained user
                              RefreshRequest / LogoutRequest deleted
  app/routers/auth.py      -> register/login set the cookie
                              refresh reads the cookie + looks up the user
                              logout clears cookie AND revokes in Redis
  tests/conftest.py        -> stateful fake Redis
  tests/test_auth.py       -> flipped assertions + full-flow test

frontend/src/
  store/authStore.ts       -> refreshToken removed
  api/auth.ts              -> refresh_token removed, no-arg logout/refresh
  pages/LoginPage.tsx      -> setAuth(token, user)
  App.tsx                  -> silent refresh on boot + checkingAuth gate
```

`dependencies/auth.py` and the CORS setup were deliberately **not** touched — the access token flow was left exactly as it was, which is what kept this change contained.

---

## Technical Lessons

### 1. httpOnly is about what an attacker can steal, not what they can do

XSS can still act inside the page. It cannot walk away with a token it is unable to read.

### 2. Split the tokens by threat model

Refresh token in a cookie (long-lived, must survive refresh, must not be readable). Access token in a header (short-lived, and header auth is CSRF-immune by construction).

### 3. Scope cookies with `path`

`path=/api/v1/auth` means the credential is only transmitted where it is actually needed.

### 4. Cookie flags must match on delete

`path`, `samesite`, `secure`, and `httponly` all have to mirror the `set_cookie` call, or the browser will not clear it.

### 5. Server-side revocation is the other half of logout

Clearing the browser's copy is not enough if a stolen copy can still be replayed. Redis is the source of truth for which tokens are live.

### 6. Gate rendering on async auth checks

Any boot-time auth request must block route rendering, or the guard will act on an answer that has not arrived.

### 7. `return_value` mocks cannot test round trips

If the code writes then reads, the fake has to hold state. `side_effect` with a backing dict is the smallest way to do that.

### 8. Assert the vulnerability is gone, not just the fix is present

`assert "refresh_token" not in data` is the assertion that actually protects against regression.

---

## Final State After This Part

- refresh tokens live only in an httpOnly, SameSite=Lax, path-scoped cookie;
- the refresh token appears nowhere in any JSON response body;
- the frontend has no reference to a refresh token anywhere in its source;
- access tokens remain in memory and are sent as Bearer headers, unchanged;
- a hard refresh silently restores the session before any route renders;
- logout clears the cookie *and* revokes the token in Redis, and is idempotent;
- the test suite proves the whole flow, backed by a Redis fake that holds state.

### Flagged, not built

Production cookie topology: `SameSite=Lax` with `secure` in production is correct **only** if the deployed frontend and backend share a registrable domain. Today that holds because the Vite proxy makes them same-origin. If a real deployment ever splits them across domains, cookies will silently stop being sent and the setup needs `SameSite=None; Secure` plus HTTPS everywhere — a separate, larger change that also touches CORS.

---

## Recap in One Diagram

```text
PHASE 10.3

LOGIN
  POST /api/v1/auth/login
    ↓
  access_token + user  ──> JSON body ──> Zustand (memory)
  refresh_token        ──> Set-Cookie: httpOnly; SameSite=Lax;
                                       path=/api/v1/auth
                           (JS can never read this)

PAGE REFRESH (F5)
  memory wiped, cookie survives
    ↓
  App boot: checkingAuth = true, render nothing
    ↓
  POST /api/v1/auth/refresh   (browser attaches cookie automatically)
    ↓ verify JWT -> check Redis -> load user -> is_active?
  new access_token + user ──> Zustand
    ↓
  checkingAuth = false ──> routes render ──> still logged in

LOGOUT
  POST /api/v1/auth/logout
    ↓
  delete_refresh_token(Redis)   <- server forgets it
  delete_cookie(matching flags) <- browser forgets it
    ↓
  clearAuth() + navigate('/login')
```