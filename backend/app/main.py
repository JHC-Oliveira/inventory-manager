import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import AsyncSessionLocal

from app.config import get_settings
from app.utils.redis_client import init_redis, close_redis, get_redis
from app.utils.rabbitmq import connect_rabbitmq, close_rabbitmq, is_rabbitmq_connected
from app.routers.auth import router as auth_router
from app.routers.product import router as product_router
from app.routers.stock import router as stock_router
from app.routers.orders import router as orders_router
from app.routers.reports import router as report_router

# ------------ Imports for Test Route ------------
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.schemas.user import UserResponse


settings = get_settings()
logger = structlog.get_logger()

def error_response(error: str, message: str, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "status_code": status_code
        }
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything BEFORE the yield runs on startup.
    Everything AFTER the yield runs on shutdown.
    """
    # ── Startup ──────────────────────────────────────────
    logger.info("application_starting", env=settings.app_env)
    await init_redis()
    logger.info("redis_connected")
    await connect_rabbitmq()      
    yield
    # ── Shutdown ─────────────────────────────────────────
    await close_redis()
    await close_rabbitmq()                                               
    logger.info("application_stopped")

app = FastAPI(
    title="Inventory Manager API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ------- Middleware (applied to every request, in order) --------

# CORS — added first in code, runs second on requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# TrustedHost — added second in code, runs FIRST on requests
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)

# ---------------- Exception handlers ----------------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    msg = str(exc).lower()

    if "not found" in msg:
        return error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)

    if "already exists" in msg or "duplicate" in msg or "conflict" in msg:
        return error_response("conflict", str(exc), status.HTTP_409_CONFLICT)

    return error_response("bad_request", str(exc), status.HTTP_400_BAD_REQUEST)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"

    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        error = "unauthorized"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        error = "forbidden"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        error = "not_found"
    elif exc.status_code == status.HTTP_409_CONFLICT:
        error = "conflict"
    else:
        error = "http_error"

    return error_response(error, detail, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        "validation_error",
        "Invalid request body",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", error=str(exc))
    return error_response(
        "internal_server_error",
        "Internal server error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ------------ Routers ------------
API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(product_router, prefix=API_PREFIX)
app.include_router(stock_router, prefix=API_PREFIX)
app.include_router(orders_router, prefix=API_PREFIX)
app.include_router(report_router, prefix=API_PREFIX)

# ------------ Protected Test Route ------------

@app.get(f"{API_PREFIX}/me", response_model=UserResponse, tags=["Users"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user. Protected route."""
    return UserResponse.model_validate(current_user)


# ------------ Health ------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Confirms the API and its dependencies are healthy.
    Used by Docker, monitoring tools, and load balancers.
    """
    checks = {
        "app": settings.app_name,
        "env": settings.app_env,
        "database": "unhealthy",
        "redis": "unhealthy",
        "rabbitmq": "unhealthy",
    }

    overall_status = "healthy"
    status_code = status.HTTP_200_OK

    # ---------------- Database ----------------
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = "unhealthy"
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("health_database_failed", error=str(exc))

    # ---------------- Redis ----------------
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as exc:
        checks["redis"] = "unhealthy"
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("health_redis_failed", error=str(exc))

    # ---------------- RabbitMQ ----------------
    try:
        if not is_rabbitmq_connected():
            raise RuntimeError("RabbitMQ connection is not available")
        checks["rabbitmq"] = "healthy"
    except Exception as exc:
        checks["rabbitmq"] = "unhealthy"
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("health_rabbitmq_failed", error=str(exc))

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            **checks,
        },
    )