import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app
from app.database import Base, get_db


@pytest_asyncio.fixture(scope="function")
async def client():
    # Fresh engine + DB per test — guaranteed isolation
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.utils.redis_client.redis_client") as mock_redis:
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=True)

        with patch("app.utils.redis_client.get_redis", AsyncMock(return_value=mock_redis)):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://localhost"
            ) as ac:
                yield ac

    app.dependency_overrides.clear()

    # Drop all tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    
    
@pytest_asyncio.fixture(scope="function")
async def user_token(client: AsyncClient) -> str:
    """Register a regular user and return their access token."""
    await client.post("/auth/register", json={
        "email": "user@example.com",
        "password": "StrongPass123",
        "full_name": "Regular User",
    })
    response = await client.post("/auth/login", data={
        "username": "user@example.com",
        "password": "StrongPass123",
    })
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def admin_token(client: AsyncClient) -> str:
    """
    Register a user then manually flip is_admin=True in the DB.
    Returns their access token.
    """
    await client.post("/auth/register", json={
        "email": "admin@example.com",
        "password": "AdminPass123",
        "full_name": "Admin User",
    })

    # Flip is_admin directly in the DB — no admin endpoint exists yet
    from app.database import get_db as real_get_db
    from sqlalchemy import update
    from app.models.user import User

    db_generator = app.dependency_overrides[real_get_db]  # direct key access, never None
    async for session in db_generator():
        await session.execute(
            update(User)
            .where(User.email == "admin@example.com")
            .values(is_admin=True)
        )
        await session.commit()
        break

    # Log in again — new token will carry is_admin=True
    response = await client.post("/auth/login", data={
        "username": "admin@example.com",
        "password": "AdminPass123",
    })
    return response.json()["access_token"]