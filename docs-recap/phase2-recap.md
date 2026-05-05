# Phase 2 Recap — JWT Authentication System

## What Phase 2 Was About

Phase 1 built the skeleton of the application — the infrastructure, the Docker setup, the database connection, the project structure. Phase 2 is where the application came alive with its first real feature: **a complete authentication system**.

By the end of Phase 2, any user can register, log in, receive tokens, make authenticated requests, refresh their session, and log out — with their password never stored in plain text and their session revocable at any time.

---

## The Big Picture — How Auth Works in This App

Before looking at individual steps, here is the complete flow:

```
REGISTRATION / LOGIN
  Client ──POST /auth/register──► Server
                                   1. Validate input (Pydantic)
                                   2. Hash password (bcrypt)
                                   3. Save user to PostgreSQL
                                   4. Generate access token (30 min)
                                   5. Generate refresh token (7 days)
                                   6. Store refresh token in Redis
                                  ◄── { access_token, refresh_token }

EVERY AUTHENTICATED REQUEST
  Client ──GET /products──────────► Server
         Authorization: Bearer ...   1. Extract token from header
                                     2. Verify signature (SECRET_KEY)
                                     3. Check expiry
                                     4. Extract user_id from payload
                                     5. No DB or Redis lookup needed
                                    ◄── { products... }

ACCESS TOKEN EXPIRES (after 30 min)
  Client ──POST /auth/refresh──────► Server
         { refresh_token }            1. Verify refresh token signature
                                      2. Check token exists in Redis
                                      3. Issue new access token
                                     ◄── { new access_token }

LOGOUT
  Client ──POST /auth/logout───────► Server
         { refresh_token }            1. Verify refresh token
                                      2. DELETE from Redis (token is dead)
                                     ◄── { message: "Logged out" }
                                      Access token expires naturally in 30 min
```

**Key insight:** The access token is stateless — the server never stores it. It just verifies the signature mathematically. The refresh token is stateful — stored in Redis so it can be revoked instantly on logout.

---

## Step 1 — Security Dependencies

Added three libraries to `requirements.txt`:

| Library | Purpose |
|---|---|
| `bcrypt==4.2.1` | Hashes passwords — intentionally slow to defeat brute force attacks |
| `python-jose[cryptography]==3.3.0` | Creates and verifies JWT tokens |
| `python-multipart==0.0.20` | Parses login form data (`application/x-www-form-urlencoded`) |

**Why bcrypt instead of passlib?** The original plan used `passlib[bcrypt]==1.7.4` but this package was last updated in 2020 and has a broken compatibility issue with `bcrypt>=4.0` — it throws a false `ValueError: password cannot be longer than 72 bytes` even for short passwords. The fix was to use `bcrypt` directly, removing the broken wrapper entirely.

**Why not MD5 or SHA256 for passwords?** Those algorithms are designed to be fast — an attacker can try billions per second. Bcrypt is intentionally slow (100ms per hash). For a real user logging in, 100ms is unnoticeable. For an attacker trying millions of passwords, it becomes computationally infeasible.

---

## Step 2 — JWT Configuration in `config.py`

Added three JWT fields to the `Settings` class:

```python
algorithm: str = "HS256"
access_token_expire_minutes: int = 30
refresh_token_expire_days: int = 7
```

**Why these specific values?**

- `HS256` (HMAC-SHA256) — the industry-standard algorithm for signing JWTs. The server runs the token's contents through HS256 with your `SECRET_KEY` to produce a unique signature. If anyone tampers with the payload, the signature won't match and the token is rejected.
- `30 minutes` — if an access token is stolen (intercepted, found in browser history), it stops working within 30 minutes. Short expiry limits damage.
- `7 days` — the refresh token lets users stay logged in for a week without re-entering their password. It's stored in Redis so it can be revoked instantly on logout, unlike the access token.

These values come from `.env` — different values for development and production without changing any code.

---

## Step 3 — The User Model (`models/user.py`)

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

**Design decisions explained:**

- **UUID instead of integer ID** — Auto-increment IDs (1, 2, 3...) are predictable. An attacker knowing `users/42` can probe `users/43`. UUIDs are random and unguessable.
- **`hashed_password` not `password`** — The real password is never stored. Ever. Even if the entire database is stolen, the attacker cannot log in as any user.
- **`index=True` on email** — Every login does `WHERE email = ?`. Without an index, PostgreSQL scans every row. With an index, it finds the match instantly regardless of table size.
- **`is_active` instead of deleting users** — This is the soft delete pattern. Permanently deleting records breaks foreign key references, loses audit history, and makes accidental deletions unrecoverable. Setting `is_active = False` hides the user from the app while preserving all their data.
- **`DateTime(timezone=True)`** — Always store timestamps in UTC. A server in Dublin and a user in Tokyo would generate conflicting local times. UTC is the universal reference.

---

## Step 4 — User Schemas (`schemas/user.py`)

Schemas are Pydantic models that define the shape of data coming **in** and going **out** of the API. They are deliberately separate from SQLAlchemy models — what you store and what you expose are often different things.

| Schema | Used When | Contains |
|---|---|---|
| `UserRegister` | POST /auth/register | email, password, full_name + validators |
| `UserResponse` | Any user data returned | id, email, full_name, is_active, is_admin — **never hashed_password** |
| `TokenResponse` | After login/register | access_token, refresh_token, token_type |
| `TokenData` | Inside JWT payload | user_id, is_admin |

**`UserRegister` validators:**
- Password: minimum 8 characters, at least one uppercase letter, at least one number
- Full name: strips whitespace, minimum 2 characters

**`model_config = {"from_attributes": True}` on `UserResponse`** — By default Pydantic only reads from dictionaries. SQLAlchemy returns objects with attributes. This setting tells Pydantic it can read from object attributes directly, enabling `UserResponse.model_validate(user_object)`.

**Why keep `TokenData` small?** JWTs are sent with every single request. Only `user_id` and `is_admin` are embedded — the minimum needed to make authorization decisions without hitting the database on every request.

---

## Step 5 — Password Utility (`utils/password.py`)

```python
import bcrypt

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
```

**What a salt is:** A random string added to the password before hashing. Without a salt, two users with the same password would produce the same hash — an attacker could precompute a table of common password hashes (called a rainbow table attack) and look yours up instantly. The salt makes every hash unique even for identical passwords. Bcrypt embeds the salt inside the hash string itself, so it's always available for verification without storing it separately.

**The mental model:**

```
REGISTRATION:   "MyPassword1"  →  hash_password()  →  "$2b$12$Eix..."  stored in DB
                "MyPassword1" is thrown away immediately — never seen again

LOGIN:          "MyPassword1" (user input) + "$2b$12$Eix..." (from DB)
                verify_password() → True  ✅ login success

ATTACKER:       "wrongpassword" + "$2b$12$Eix..." (from DB)
                verify_password() → False  ❌ login denied
```

---

## Step 6 — JWT Utility (`utils/jwt.py`)

Three functions:

**`create_access_token(user_id, is_admin)`** — Builds a short-lived token with this payload:
```python
{
    "sub": user_id,      # standard JWT field — the subject (who this token belongs to)
    "is_admin": is_admin, # custom claim — permission level
    "exp": expire,        # standard JWT field — checked automatically by the library
    "type": "access"      # custom claim — prevents token type confusion attacks
}
```

**`create_refresh_token(user_id)`** — Same structure but `type: "refresh"` and 7-day expiry.

**`verify_token(token, expected_type)`** — Called on every protected request:
1. `jwt.decode()` automatically verifies the signature and checks expiry
2. Manually checks `user_id` exists in payload
3. Checks `type` matches `expected_type` — prevents a client from sending a refresh token where an access token is expected

**Why the `type` field?** Both access and refresh tokens are signed with the same `SECRET_KEY`. Without a type field, a client could send a refresh token on a protected route and it would pass signature verification. The `type` field explicitly rejects the wrong kind.

---

## Step 7 — Redis Utility (`utils/redis_client.py`)

Redis is an in-memory key-value store. Think of it as a Python dictionary that lives outside the app, survives restarts, and automatically deletes keys after a set time.

```python
# Key naming convention — colons create logical namespaces
f"refresh_token:{user_id}"   # e.g. refresh_token:a3f8c2d1-...

store_refresh_token()  # redis.setex(key, 7_days_in_seconds, token)
get_refresh_token()    # redis.get(key)          → token string or None
delete_refresh_token() # redis.delete(key)       → token is gone forever
```

**`setex` = SET with EXpiry** — stores the value AND sets automatic expiry in one atomic operation. After 7 days Redis automatically deletes the key. No cron job needed.

**Why Redis is critical for logout:**

```
WITHOUT Redis:  User logs out → token deleted from client
                Attacker still has a copy → still works for 30 min ❌

WITH Redis:     User logs out → refresh_token:{id} deleted from Redis
                Attacker tries to refresh → Redis returns None → rejected ✅
                Access token expires naturally within 30 min → fully locked out ✅
```

The Redis client is initialised once on app startup via `lifespan` in `main.py` and closed on shutdown — the same pattern as the SQLAlchemy engine.

---

## Step 8 — Auth Router (`routers/auth.py`)

Four endpoints that bring everything together:

| Endpoint | Method | What it does | Returns |
|---|---|---|---|
| `/auth/register` | POST | Validates input, hashes password, saves user, issues tokens | 201 + TokenResponse |
| `/auth/login` | POST | Verifies credentials, issues tokens | 200 + TokenResponse |
| `/auth/refresh` | POST | Validates refresh token, checks Redis, issues new access token | 200 + TokenResponse |
| `/auth/logout` | POST | Validates refresh token, deletes from Redis | 200 + message |

**Security decisions in the router:**

- Login returns the same `401 Unauthorized` whether the email doesn't exist or the password is wrong — never reveal which one failed. This prevents user enumeration attacks.
- `await db.flush()` gets the generated UUID before committing, so it can be used in the token payload. `await db.commit()` persists the user immediately within the request.

---

## Step 9 — Auth Dependency (`dependencies/auth.py`)

```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    # 1. Verify JWT signature and expiry
    # 2. Look up user in DB by user_id from token
    # 3. Check user is active
    # 4. Return user object

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    # Raises 403 if is_admin is False
```

Any route that needs authentication adds `current_user: User = Depends(get_current_user)` to its signature. FastAPI handles the entire token extraction, verification, and user lookup automatically. Protected routes don't need to know anything about JWTs.

---

## Step 10 — Wiring into `main.py`

Redis init/close added to the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()    # runs ONCE on startup
    yield
    await close_redis()   # runs ONCE on shutdown
```

A test protected route was added:

```python
@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
```

---

## Step 11 — Tests (`tests/test_auth.py`)

Eight tests covering the full auth surface:

| Test | What it verifies |
|---|---|
| `test_register_success` | 201, tokens returned, no password exposed |
| `test_register_duplicate_email` | 409 on duplicate |
| `test_login_success` | 200, tokens returned |
| `test_login_wrong_password` | 401 |
| `test_login_nonexistent_user` | 401 |
| `test_protected_route_with_valid_token` | 200 with valid Bearer token |
| `test_protected_route_without_token` | 401 |
| `test_protected_route_with_invalid_token` | 401 |

**Test infrastructure decisions:**

- **SQLite in-memory** (`sqlite+aiosqlite:///:memory:`) instead of PostgreSQL — fast, isolated, no Docker dependency for tests
- **Engine created inside the fixture** — each test gets its own brand new database, guaranteed isolation
- **Redis fully mocked** with `unittest.mock.AsyncMock` — tests never need a real Redis connection. `store_refresh_token`, `get_refresh_token`, and `delete_refresh_token` are all intercepted

**Lesson learned — `flush()` vs `commit()` in SQLite tests:** SQLite handles connections differently from PostgreSQL. A `flush()` without `commit()` means data from one request isn't visible to the next request's new session in SQLite. The fix was adding `await db.commit()` explicitly in the router after `flush()`. This is safe — a second commit on an already-committed session is a no-op in SQLAlchemy.

---

## Bugs Fixed Along the Way

| Bug | Cause | Fix |
|---|---|---|
| `ValueError: password cannot be longer than 72 bytes` | `passlib 1.7.4` broken with `bcrypt>=4.0` | Replaced passlib with `bcrypt` directly |
| `RuntimeError: Redis client is not initialised` | `lifespan` doesn't run in tests | Mocked Redis with `AsyncMock` in conftest |
| Duplicate email test returning 201 | SQLite file persisted between tests | Switched to `:///:memory:` and engine-per-fixture |
| Login returning 401 after register | `flush()` without `commit()` not visible across SQLite sessions | Added `await db.commit()` in register endpoint |
| Tests hitting wrong route `/users/me` | Route is `/me` in `main.py` | Fixed test to use `/me` |

---

## Phase 2 Security Habits Established

1. **Never store plain passwords** — only bcrypt hashes
2. **Never expose `hashed_password`** — `UserResponse` schema deliberately omits it
3. **Short-lived access tokens** — 30 minutes limits damage from theft
4. **Revocable refresh tokens** — Redis makes logout truly work
5. **Token type claims** — prevents refresh tokens being used as access tokens
6. **Vague error messages on login** — never reveal if email or password was wrong
7. **UUID primary keys** — unguessable user IDs

---

## What's Next — Phase 3

Phase 3 will build the **Product model and CRUD endpoints** — the first real business feature of the Inventory Manager. It will follow the same pattern established here: model → schemas → service layer → router → tests.
