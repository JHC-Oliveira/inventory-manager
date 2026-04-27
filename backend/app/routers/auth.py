import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, TokenResponse
from app.utils.password import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, verify_token
from app.utils.redis_client import (
    store_refresh_token,
    get_refresh_token,
    delete_refresh_token,
)
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and return tokens."""

    # 1. Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # 2. Create the user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(new_user)
    await db.flush()  # sends INSERT to DB, gets the generated id, but doesn't commit yet

    # 3. Generate tokens
    access_token = create_access_token(user_id=new_user.id, is_admin=new_user.is_admin)
    refresh_token = create_refresh_token(user_id=new_user.id)

    # 4. Store refresh token in Redis
    await store_refresh_token(
        user_id=new_user.id,
        token=refresh_token,
        expire_days=settings.refresh_token_expire_days,
    )

    logger.info("user_registered", user_id=new_user.id, email=new_user.email)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login with email and password, returns tokens."""

    # 1. Find user by email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # 2. Verify user exists and password is correct
    # We check both in one block intentionally — never reveal which one failed
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    # 4. Generate tokens
    access_token = create_access_token(user_id=user.id, is_admin=user.is_admin)
    refresh_token = create_refresh_token(user_id=user.id)

    # 5. Store refresh token in Redis
    await store_refresh_token(
        user_id=user.id,
        token=refresh_token,
        expire_days=settings.refresh_token_expire_days,
    )

    logger.info("user_logged_in", user_id=user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token: str):
    """Issue a new access token using a valid refresh token."""

    # 1. Verify the token is a valid JWT refresh token
    try:
        token_data = verify_token(token, expected_type="refresh")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # 2. Check if the token exists in Redis (not logged out)
    stored_token = await get_refresh_token(user_id=token_data.user_id)
    if stored_token is None or stored_token != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has been revoked",
        )

    # 3. Issue a new access token
    new_access_token = create_access_token(
        user_id=token_data.user_id,
        is_admin=token_data.is_admin,
    )

    logger.info("token_refreshed", user_id=token_data.user_id)

    return TokenResponse(access_token=new_access_token, refresh_token=token)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(token: str):
    """Logout by revoking the refresh token."""

    # 1. Verify it's a valid refresh token
    try:
        token_data = verify_token(token, expected_type="refresh")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # 2. Delete from Redis — token is now dead
    await delete_refresh_token(user_id=token_data.user_id)

    logger.info("user_logged_out", user_id=token_data.user_id)

    return {"message": "Successfully logged out"}