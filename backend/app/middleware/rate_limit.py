import time

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.redis_client import get_redis

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        exempt_paths: set[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.exempt_paths = exempt_paths or {"/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        current_window = int(time.time() // self.window_seconds)
        redis_key = f"rate_limit:{client_ip}:{current_window}"

        try:
            redis = await get_redis()
            current_count = await redis.incr(redis_key)

            if current_count == 1:
                await redis.expire(redis_key, self.window_seconds)

            remaining = max(self.requests_per_minute - current_count, 0)
            reset_seconds = self.window_seconds - (int(time.time()) % self.window_seconds)

            if current_count > self.requests_per_minute:
                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    path=request.url.path,
                    method=request.method,
                    limit=self.requests_per_minute,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "status_code": 429,
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_seconds),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_seconds)
            return response

        except Exception as exc:
            logger.warning("rate_limit_check_failed", error=str(exc))
            return await call_next(request)