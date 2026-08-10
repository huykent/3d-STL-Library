"""FastAPI dependency providers: DB session, current user, admin guard."""
from __future__ import annotations

from typing import AsyncGenerator

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the JWT and return the corresponding User row.

    Raises 401 if the token is invalid/expired or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    settings = get_settings()
    try:
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenPayload(sub=username, role=role)
    except pyjwt.PyJWTError:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.username == token_data.sub)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the current user, raising 401 if they are inactive."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )
    return current_user


async def get_current_active_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Return the current user, raising 403 if they are not an admin."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
