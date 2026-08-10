"""Admin router: user management and source group management.

All endpoints require admin role via get_current_active_admin dependency.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_admin, get_db
from app.models.source_group import SourceGroup
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter()


# ── SourceGroup schemas (admin-only, defined here for locality) ───────────

class SourceGroupOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    chat_id: int
    name: str
    username: Optional[str]
    is_active: bool
    model_count: int
    last_message_id: Optional[int]


class SourceGroupCreate(BaseModel):
    chat_id: int
    name: str
    username: Optional[str] = None
    is_active: bool = True


# ── Users ─────────────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=List[UserOut],
    summary="List all registered users (admin only)",
)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
) -> List[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


# ── Source Groups ─────────────────────────────────────────────────────────

@router.get(
    "/groups",
    response_model=List[SourceGroupOut],
    summary="List all Telegram source groups (admin only)",
)
async def list_groups(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
) -> List[SourceGroupOut]:
    result = await db.execute(select(SourceGroup).order_by(SourceGroup.id))
    groups = result.scalars().all()
    return [SourceGroupOut.model_validate(g) for g in groups]


@router.post(
    "/groups",
    response_model=SourceGroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Telegram source group (admin only)",
)
async def create_group(
    body: SourceGroupCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
) -> SourceGroupOut:
    """Add a new Telegram group to the crawler's watch list."""
    # Check for duplicate
    existing = await db.execute(
        select(SourceGroup).where(SourceGroup.chat_id == body.chat_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Group with chat_id {body.chat_id} already exists",
        )

    group = SourceGroup(
        chat_id=body.chat_id,
        name=body.name,
        username=body.username,
        is_active=body.is_active,
    )
    db.add(group)
    await db.flush()
    return SourceGroupOut.model_validate(group)
