from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from app.config import get_settings
from app.schemas.user import TokenData

settings = get_settings()


def create_access_token(user_id: str, is_admin: bool = False) -> str:
    """
    Creates a short-lived JWT access token.
    Embeds user_id and is_admin into the payload.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "is_admin": is_admin,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: str) -> str:
    """
    Creates a long-lived JWT refresh token.
    Contains minimal data — only used to issue new access tokens.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str, expected_type: str) -> TokenData:
    """
    Decodes and validates a JWT token.
    Raises ValueError if the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        ) 

        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        is_admin: bool = payload.get("is_admin", False)

        if user_id is None:
            raise ValueError("Token is missing user identity")

        if token_type != expected_type:
            raise ValueError(f"Expected {expected_type} token, got {token_type}")

        return TokenData(user_id=user_id, is_admin=is_admin)

    except JWTError:
        raise ValueError("Token is invalid or has expired")