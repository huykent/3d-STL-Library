"""Auth service: password hashing, verification, and JWT token creation.

Uses the ``bcrypt`` library directly (compatible with bcrypt ≥ 4.x) instead of
passlib, which has a known incompatibility with bcrypt ≥ 4.0 (missing __about__).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt

from app.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches the stored *hashed_password*."""
    try:
        if not plain_password or not hashed_password:
            return False
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False



def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The username (stored in ``sub`` claim).
        role:    The user role (e.g. ``"admin"`` or ``"viewer"``).
        expires_delta: Optional custom duration for token expiration.

    Returns:
        A signed JWT string.
    """
    settings = get_settings()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
