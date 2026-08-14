from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_admin, get_current_active_user, get_db
from app.models.model3d import Model3D
from app.models.user import User, UserRole
from app.models.user_data import UserDownload, UserFavorite
from app.services.auth_service import get_password_hash, verify_password

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None


class UserAdminUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class FavoriteCreate(BaseModel):
    model_id: uuid.UUID


class DownloadCreate(BaseModel):
    model_id: uuid.UUID


# ── Admin Endpoints ───────────────────────────────────────────────
@router.get("/admin/list", response_model=List[UserResponse], summary="List all users (Admin)")
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> List[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/admin/{user_id}", response_model=UserResponse, summary="Update user (Admin)")
async def admin_update_user(
    user_id: uuid.UUID,
    update_data: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if update_data.role is not None:
        user.role = update_data.role
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
        
    await db.commit()
    await db.refresh(user)
    return user


# ── User Profile ──────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.put("/me", response_model=UserResponse, summary="Update current user profile")
async def update_me(
    update_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    if update_data.email:
        current_user.email = update_data.email
    if update_data.password:
        current_user.password_hash = get_password_hash(update_data.password)
        
    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── User Favorites ────────────────────────────────────────────────
@router.get("/me/favorites", summary="Get user's favorite models")
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Model3D)
        .join(UserFavorite, Model3D.id == UserFavorite.model_id)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(UserFavorite.created_at.desc())
    )
    models = result.scalars().all()
    # Mock pagination response structure to match /api/models
    return {"items": models, "total": len(models), "has_next": False}


@router.post("/me/favorites", summary="Add a model to favorites")
async def add_favorite(
    data: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Check if exists
    result = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.model_id == data.model_id,
        )
    )
    if result.scalar_one_or_none():
        return {"status": "already_exists"}
        
    fav = UserFavorite(user_id=current_user.id, model_id=data.model_id)
    db.add(fav)
    await db.commit()
    return {"status": "added"}


@router.delete("/me/favorites/{model_id}", summary="Remove a model from favorites")
async def remove_favorite(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.model_id == model_id,
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await db.delete(fav)
        await db.commit()
    return {"status": "removed"}


# ── User History ──────────────────────────────────────────────────
@router.get("/me/history", summary="Get user's download history (models)")
async def get_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Model3D)
        .join(UserDownload, Model3D.id == UserDownload.model_id)
        .where(UserDownload.user_id == current_user.id)
        .order_by(UserDownload.downloaded_at.desc())
    )
    models = result.scalars().all()
    # Mock pagination response structure
    return {"items": models, "total": len(models), "has_next": False}


@router.post("/me/history", summary="Record a model download")
async def record_download(
    data: DownloadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    record = UserDownload(user_id=current_user.id, model_id=data.model_id)
    db.add(record)
    await db.commit()
    return {"status": "recorded"}
