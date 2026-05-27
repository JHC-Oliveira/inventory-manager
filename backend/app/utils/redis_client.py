import json
from typing import Any

import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

# The Redis client instance — created once, reused across requests
redis_client: aioredis.Redis | None = None

# -------------- Connection lifecycle ----------------

async def get_redis() -> aioredis.Redis:
    """
    Returns the active Redis client.
    Raises RuntimeError if Redis hasn't been initialised yet.
    """
    if redis_client is None:
        raise RuntimeError("Redis client is not initialised")
    return redis_client


async def init_redis() -> None:
    """
    Creates the Redis connection.
    Called once on application startup inside lifespan.
    """
    global redis_client
    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    """
    Closes the Redis connection.
    Called once on application shutdown inside lifespan.
    """
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None

# ------------- Auth token helpers ------------------------

async def store_refresh_token(user_id: str, token: str, expire_days: int) -> None:
    """
    Saves a refresh token in Redis tied to a user.
    Automatically expires after expire_days.
    """
    client = await get_redis()
    key = f"refresh_token:{user_id}"
    expire_seconds = expire_days * 24 * 60 * 60
    await client.setex(key, expire_seconds, token)


async def get_refresh_token(user_id: str) -> str | None:
    """
    Retrieves the stored refresh token for a user.
    Returns None if it doesn't exist or has expired.
    """
    client = await get_redis()
    key = f"refresh_token:{user_id}"
    return await client.get(key)


async def delete_refresh_token(user_id: str) -> None:
    """
    Deletes a user's refresh token from Redis.
    Called on logout — invalidates the token immediately.
    """
    client = await get_redis()
    key = f"refresh_token:{user_id}"
    await client.delete(key)
    
# -------------- Cache helpers ----------------

async def cache_get(key: str) -> Any | None:
    """
    Reads a cached value from Redis.
    Returns the deserialised Python object, or None on a cache miss.
    """
    client = await get_redis()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """
    Stores a value in Redis as JSON with a TTL in seconds.
    ttl=300 → expires in 5 minutes.
    """
    client = await get_redis()
    await client.setex(key, ttl, json.dumps(value))


async def cache_delete(key: str) -> None:
    """
    Removes a single exact key from the cache.
    Used when one specific cached entry must be invalidated.
    """
    client = await get_redis()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    """
    Deletes all keys matching a glob pattern using SCAN.
    Used for cache invalidation on write, e.g. pattern="products:list:*"
    removes every paginated product list at once.

    SCAN is used instead of KEYS to avoid blocking Redis on large keyspaces.
    """
    client = await get_redis()
    cursor = 0
    while True:
        cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await client.delete(*keys)
        if cursor == 0:
            break