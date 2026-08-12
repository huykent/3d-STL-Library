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


# ── Settings ──────────────────────────────────────────────────────────────

from typing import Dict
from app.services.settings import SettingsService
from app.telegram.client import restart_telegram_client, get_telegram_client

@router.get(
    "/settings",
    response_model=Dict[str, str],
    summary="Get all system settings (admin only)",
)
async def get_settings_api(
    _admin: User = Depends(get_current_active_admin),
) -> Dict[str, str]:
    return await SettingsService.get_all_settings()


@router.post(
    "/settings",
    summary="Update system settings (admin only)",
)
async def update_settings_api(
    new_settings: Dict[str, str],
    _admin: User = Depends(get_current_active_admin),
):
    await SettingsService.update_settings(new_settings)
    return {"status": "success", "message": "Settings updated successfully"}


@router.post(
    "/telegram/restart",
    summary="Restart Telegram Crawler Client (admin only)",
)
async def restart_crawler_api(
    _admin: User = Depends(get_current_active_admin),
):
    try:
        await restart_telegram_client()
        return {"status": "success", "message": "Telegram client restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ManualCrawlRequest(BaseModel):
    chat_id: int
    limit: Optional[int] = 1

@router.post(
    "/telegram/crawl-history",
    summary="Manually trigger a history crawl for a group (admin only)",
)
async def manual_crawl_history_api(
    body: ManualCrawlRequest,
    _admin: User = Depends(get_current_active_admin),
):
    try:
        from app.worker.queue import get_redis_pool
        redis = await get_redis_pool()
        await redis.enqueue_job(
            'manual_crawl_history', 
            chat_id=body.chat_id, 
            limit=body.limit
        )
        return {"status": "success", "message": f"Queued manual crawl for group {body.chat_id}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class SendCodeRequest(BaseModel):
    phone: str

@router.post(
    "/telegram/send-code",
    summary="Send OTP code to Telegram phone (admin only)",
)
async def send_code_api(
    body: SendCodeRequest,
    _admin: User = Depends(get_current_active_admin),
):
    try:
        client = await get_telegram_client()
        if not client.is_connected():
            await client.connect()
        sent_code = await client.send_code_request(body.phone)
        return {"status": "success", "phone_code_hash": sent_code.phone_code_hash}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

class OTPVerification(BaseModel):
    phone: str
    code: str
    phone_code_hash: str
    password: Optional[str] = None

@router.post(
    "/telegram/verify-otp",
    summary="Submit Telegram OTP to complete login (admin only)",
)
async def verify_otp_api(
    body: OTPVerification,
    _admin: User = Depends(get_current_active_admin),
):
    try:
        from telethon.errors import SessionPasswordNeededError
        client = await get_telegram_client()
        
        try:
            await client.sign_in(body.phone, body.code, phone_code_hash=body.phone_code_hash)
        except SessionPasswordNeededError:
            if not body.password:
                return {"status": "password_needed", "message": "2FA Password is required"}
            await client.sign_in(password=body.password)
            
        # Save the string session to database so it persists and worker can use it
        session_string = client.session.save()
        await SettingsService.update_settings({"TELEGRAM_SESSION_STRING": session_string})
        
        return {"status": "success", "message": "Logged in successfully"}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to verify telegram OTP")
        raise HTTPException(status_code=400, detail=str(e))
