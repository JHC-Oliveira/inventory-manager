# CLAUDE.md — Inventory Manager

## Stack & Architecture
- **Backend:** FastAPI (async) · PostgreSQL + SQLAlchemy (async) + Alembic · Redis (refresh
  tokens, cache, rate-limit) · RabbitMQ (low-stock events) + worker · Docker Compose.
  Tests: pytest + httpx on in-memory SQLite.
- **Frontend** (`frontend/`): React 19 + Vite + TypeScript · Zustand (auth) · TanStack Query
  · React Router · react-hook-form + Zod · Tailwind + shadcn/radix · axios.
- **Flow:** `Router → Service → DB / Redis / RabbitMQ → response schema`.
  Frontend: `page → src/api/*.ts → backend /api/v1`.

## Inviolable conventions
- **Routers handle HTTP only; services own business logic — no DB access in routers.**
  Exception: `auth.py` still queries the DB directly; do not copy it, new features use a service.
- **Services raise `ValueError`, not HTTPException.** The global handler in `main.py` maps the
  message to a status ("not found"→404, "already exists"/"conflict"→409, else 400). Prefer this
  over catch-and-convert inside routers. Known drift: product/orders/stock routers still
  catch `ValueError` and map it themselves too (redundant, not yet cleaned up) — `reports.py`
  is the one router that already relies on the global handler only; match that, not the others.
- **One error envelope everywhere:** `{ error, message, status_code }`.
- **Admin writes, any authenticated user reads** — enforce via `get_current_admin` / `get_current_user`.
- **Publish to RabbitMQ only after the DB commit succeeds.**
- **Cache with explicit invalidation** — never serve stale data for speed.
- Async SQLAlchemy everywhere · prefixed IDs · structured logs (structlog).
- **Secrets only in `.env` (never committed). Security is the top priority.**
- **Frontend:** all API calls go through `src/api/client.ts` (axios, injects Bearer token);
  auth state lives in `src/store/authStore.ts`.

## Roadmap
Backend phases 1–9 complete: CRUD + auth (2–3), stock + RabbitMQ worker (4–6), Redis caching
(7), reports/analytics (8), and the production layer — error envelope, `/api/v1` versioning,
dependency-aware health checks, request logging, rate limiting (9).
**Phase 10 — React frontend** (`frontend` branch), in progress. Done: login/register, protected
routes, product dashboard CRUD. Remaining: stock adjustment UI, order management UI, low-stock
dashboard. No recap exists for Phase 10 yet.

## Recaps
Per-phase backend history: `docs-recap/phase1-recap.md … phase9-recap.md`. Read the relevant
one before changing behaviour a phase established (auth, stock, orders, caching, reports, ops
layer) — they are the source of truth for *why*. This file is only the map.
