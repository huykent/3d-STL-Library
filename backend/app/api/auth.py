"""Auth router: POST /login."""
from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.services.auth_service import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=Token, summary="Obtain JWT access token")
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate with username + password and receive a JWT access token."""
    try:
        # Look up user by username
        result = await db.execute(
            select(User).where(User.username == credentials.username)
        )
        user = result.scalar_one_or_none()

        # Unified 401 for wrong user OR wrong password (avoid username enumeration)
        if user is None or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
            )

        # Check remember_me parameter from form data or query parameters
        is_remember = False
        try:
            form_data = await request.form()
            remember_val = (
                form_data.get("remember_me")
                or form_data.get("remember")
                or request.query_params.get("remember_me")
                or request.query_params.get("remember")
            )
            if remember_val is not None:
                is_remember = str(remember_val).strip().lower() in ("true", "1", "yes", "on")
        except Exception:
            pass

        # 30 days if remember_me is enabled, otherwise 1 day
        expires_delta = timedelta(days=30) if is_remember else timedelta(days=1)

        role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
        token = create_access_token(
            subject=user.username,
            role=role_str,
            expires_delta=expires_delta,
        )
        return Token(access_token=token)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Login internal error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )

