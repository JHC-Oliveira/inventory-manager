import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

# The Redis client instance — created once, reused across requests
redis_client: aioredis.Redis | None = None


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