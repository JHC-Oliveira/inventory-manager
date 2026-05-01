import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.utils.redis_client import init_redis, close_redis
from app.routers.auth import router as auth_router

# ------------ Imports for Test Route ------------
from fastapi import Depends
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.schemas.user import UserResponse


settings = get_settings()
logger = structlog.get_logger()


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
    yield
    # ── Shutdown ─────────────────────────────────────────
    await close_redis()
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# TrustedHost — added second in code, runs FIRST on requests
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)



# ------------ Routers ------------

app.include_router(auth_router)


# ------------ Protected Test Route (It will be taken out in phase 3) ------------

@app.get("/me", response_model=UserResponse, tags=["System"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user. Protected route."""
    return current_user


# ------------ Health ------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Confirms the API is alive and which environment it's running in.
    Used by Docker, monitoring tools, and load balancers.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "env": settings.app_env,
    }