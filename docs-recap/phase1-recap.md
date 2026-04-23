# Phase 1 — Project Foundation

### Your Complete Recap & Study Reference

---

## What Phase 1 Was About

Phase 1 was about building the **skeleton** of a professional full-stack application. No features, no business logic — just the infrastructure that everything else will sit on top of. Think of it as building the foundation of a house before any walls go up.

---

## Step 1 — Project Structure

**What we did:** Created the folder structure for the entire project.

**Key lesson:**

> Separation of concerns — each folder has one clear responsibility. `routers/` handles HTTP, `services/` handles business logic, `models/` handles database tables, `schemas/` handles data validation. When a bug happens you know exactly which folder to open.

```
backend/app/
├── models/      ← database tables
├── schemas/     ← request/response shapes
├── routers/     ← API endpoints
├── services/    ← business logic
├── middleware/  ← security layers
└── utils/       ← shared helpers
```

---

## Step 2 — `.gitignore`

**What we did:** Told Git which files to never track.

**Key lesson:**

> Your `.env` file contains passwords and secret keys. One accidental `git push` exposes them forever. The `.gitignore` is your first line of security defence. **Never commit secrets.**

```gitignore
.env        ← real secrets, never committed
*.env
__pycache__/
venv/
```

---

## Step 3 — `.env` and `.env.example`

**What we did:** Created two files — one with real secrets, one safe template for Git.

**Key lesson:**

> Two files serve two different purposes. `.env` stays on your machine only. `.env.example` is committed to Git as a blueprint so teammates know what variables they need to fill in — without exposing real values.

**Critical security habits learned:**

- Always generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`
- Never use passwords you've seen in a tutorial — they're the first ones attackers try

---

## Step 4 — `requirements.txt`

**What we did:** Listed all Python dependencies with pinned versions.

**Key lesson:**

> Pinning exact versions with `==` guarantees your app behaves identically on every machine. Without pinning, `pip` could install a newer breaking version tomorrow and your app silently breaks.

**Progressive approach learned:**

> Only install what you need **right now**. Add libraries as you reach the phase that uses them — this way you learn each library when you're actually working with it.

| Package               | Role                                                   |
| --------------------- | ------------------------------------------------------ |
| `fastapi`             | The web framework — receives requests, sends responses |
| `uvicorn`             | The server that runs FastAPI                           |
| `sqlalchemy[asyncio]` | Translates Python into SQL queries                     |
| `asyncpg`             | Low-level PostgreSQL driver                            |
| `alembic`             | Database migration manager                             |
| `pydantic`            | Validates request/response data                        |
| `pydantic-settings`   | Validates environment variables                        |
| `structlog`           | Structured JSON logging                                |

---

## Step 5 — `config.py`

**What we did:** Created a centralised, validated settings manager.

### Pydantic Settings acts as a contract

```python
database_url: str        # No default = MUST exist in .env or app refuses to start
app_name: str = "..."    # Has default = optional in .env
```

If a required variable is missing, the app fails immediately with a clear error — not mysteriously later.

### `@lru_cache` — read `.env` once, cache forever

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Without this, every request would re-read the `.env` file from disk. With it — read once, serve from memory always.

### `@property` — computed attribute

```python
@property
def allowed_origins_list(self) -> list[str]:
    return [origin.strip() for origin in self.allowed_origins.split(",")]
```

Looks like a variable, behaves like a function. No parentheses needed when accessing it.

### Lessons learned from errors

**VS Code / Pylance false warning:**

> Pylance (static analyser) complains about fields with no default because it can't read `.env` at analysis time. Adding `= ""` silences the false warning without affecting runtime behaviour.

**Pydantic extra fields error:**

> Pydantic rejects `.env` variables not defined in `Settings`. Fix with `extra="ignore"` — tells Pydantic to silently skip unknown variables. Essential for a progressive approach where `.env` has future variables not yet declared.

---

## Step 6 — `database.py`

**What we did:** Built the bridge between Python and PostgreSQL.

### Three components, three responsibilities

| Component           | What it is                    | Analogy        |
| ------------------- | ----------------------------- | -------------- |
| `engine`            | Connection pool to PostgreSQL | The phone line |
| `AsyncSessionLocal` | Session factory               | A phone call   |
| `Base`              | Parent class for all models   | The template   |

### Why async matters

> Synchronous DB calls block the server — while waiting for PostgreSQL, no other requests can be handled. Async means thousands of requests can be served concurrently while waiting on I/O.

### Key configuration options

- **`pool_pre_ping=True`** — tests each connection before using it. If PostgreSQL restarted (common in Docker), dead connections are detected and replaced instead of causing mysterious errors.
- **`expire_on_commit=False`** — without this, SQLAlchemy "expires" objects after a commit, meaning accessing any attribute would trigger another DB query. Setting to `False` keeps objects usable in memory after commit.

### The `get_db()` dependency pattern

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session          # hands session to the route
            await session.commit() # success = save everything
        except Exception:
            await session.rollback() # failure = undo everything
            raise
```

Either everything succeeds together or nothing is saved — this is the **transaction safety** principle.

---

## Step 7 — `main.py`

**What we did:** Created the entry point of the application with security middleware.

### `lifespan` controls startup/shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs ONCE on startup
    yield
    # runs ONCE on shutdown
```

In future phases this will open RabbitMQ connections on startup and close them cleanly on shutdown.

### Hide Swagger in production

```python
docs_url="/docs" if settings.debug else None
```

Swagger exposes your entire API surface. In production `DEBUG=false` makes the `/docs` route not exist at all — attackers can't explore what they can't see.

### Middleware order — critical lesson

> FastAPI applies middleware in **reverse registration order**. The last one added runs first on incoming requests. Most restrictive checks must be added last.

```python
# CORS added first → runs second on every request
app.add_middleware(CORSMiddleware, ...)

# TrustedHost added second → runs FIRST on every request
app.add_middleware(TrustedHostMiddleware, ...)
```

**What each middleware does:**

| Middleware              | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `TrustedHostMiddleware` | Rejects requests with forged `Host` headers       |
| `CORSMiddleware`        | Controls which frontend domains can call your API |

---

## Step 8 — `Dockerfile` & `docker-compose.yml`

**What we did:** Containerised the entire application stack.

### Docker layer caching trick

```dockerfile
COPY requirements.txt .     # copy this first
RUN pip install ...         # install dependencies (cached layer)
COPY . .                    # copy code second
```

Dependencies change rarely, code changes constantly. Copying them separately means Docker skips the slow `pip install` on every code rebuild.

### Never run as root in containers

```dockerfile
RUN useradd --create-home appuser
USER appuser
```

If an attacker exploits your app, a non-root user is contained — it can't escape to the host machine.

### `depends_on` with `condition: service_healthy`

> Without health checks, Docker starts your API the instant PostgreSQL's container starts — but PostgreSQL takes seconds to be actually ready. Health checks make Docker wait until each service genuinely accepts connections before starting the API.

**Startup order enforced:**

```
PostgreSQL healthy → Redis healthy → RabbitMQ healthy → API starts
```

### Docker networking

> Containers on the same network reach each other by **service name**. Your API connects to `postgres:5432` — Docker resolves `postgres` to the container's IP automatically. This only works inside Docker.

### Named volumes

> Without named volumes, every `docker compose down` would wipe your entire database. Named volumes persist data between container restarts and rebuilds.

---

## Step 9 — Alembic

**What we did:** Set up database migration management.

### Think of Alembic as Git for your database schema

> Every table change is tracked, versioned, and repeatable. Every environment — your laptop, teammates, production — applies the exact same changes in the exact same order.

### Never hardcode DB credentials in `alembic.ini`

```python
# Inject from .env programmatically instead
config.set_main_option("sqlalchemy.url", settings.database_url)
```

### The model registration trick

```python
import app.models  # noqa: F401
```

Models only register with `Base.metadata` when imported. Without this line, Alembic sees an empty schema and thinks no tables should exist.

### Critical Docker lesson learned

> Always run Alembic **inside** the container, not from your local machine:

```bash
# Correct — runs inside Docker where 'postgres' hostname resolves
docker compose exec api alembic current

# Wrong — your laptop doesn't know what 'postgres' means
alembic current
```

| Where you run           | PostgreSQL hostname |
| ----------------------- | ------------------- |
| Inside Docker container | `postgres`          |
| Local machine           | `localhost`         |

---

## Phase 1 — The Big Picture

Every file created serves a specific, non-overlapping purpose:

```
.env               → secrets (never in Git)
config.py          → reads and validates secrets
database.py        → connects to PostgreSQL
main.py            → starts the app, applies security rules
Dockerfile         → packages the app into a container
docker-compose.yml → wires all 4 services together
alembic/           → manages database schema changes
```

## Security Habits Established in Phase 1

1. Secrets in `.env`, never in code or Git
2. Non-root Docker user
3. Middleware rejects bad requests before your code runs
4. Swagger hidden in production
5. Health checks ensure services are genuinely ready before API starts
6. Connection pooling with dead connection detection (`pool_pre_ping`)
7. Transaction safety — rollback on any error, commit only on full success

---

*Next: Phase 2 — JWT Authentication*
