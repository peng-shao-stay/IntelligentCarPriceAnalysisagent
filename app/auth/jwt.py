"""
JWT token creation and decoding.
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.core.config import settings


def create_access_token(user_id: int, role: str) -> str:
    """Create a JWT access token containing user_id and role."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode a JWT access token. Returns None if invalid or expired."""
    try:
        return pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except pyjwt.PyJWTError:
        return None
