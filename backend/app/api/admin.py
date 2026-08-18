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
    
    # Auto-sync TELEGRAM_CHAT_IDS to source_groups table
    from app.services.source_group_sync import sync_source_groups_from_settings
    await sync_source_groups_from_settings()

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


# ── Queue Status API ──────────────────────────────────────────────────────

from app.models.model3d import Model3D, ProcessingStatus

@router.get(
    "/queue/status",
    summary="Get real-time worker processing status and queue stats (admin/user)",
)
async def get_queue_status_api(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_admin),
):
    """Returns status data organized into 4 logical blocks for dashboard UI."""
    from app.models.source_group import SourceGroup
    from app.services.settings import SettingsService
    from app.config import get_settings
    from datetime import datetime
    from sqlalchemy import func

    # Auto-sync TELEGRAM_CHAT_IDS to source_groups DB table
    from app.services.source_group_sync import sync_source_groups_from_settings
    await sync_source_groups_from_settings(session=db)

    # Target chat ID setting
    target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
    if not target_chat_str:
        target_chat_str = get_settings().TELEGRAM_TARGET_CHAT_ID

    # Query active models currently processing
    stmt_active = (
        select(Model3D, SourceGroup.name)
        .outerjoin(SourceGroup, Model3D.source_group_id == SourceGroup.id)
        .where(Model3D.processing_status == ProcessingStatus.processing)
        .order_by(Model3D.updated_at.desc())
    )
    res_active = await db.execute(stmt_active)
    active_rows = res_active.all()

    active_jobs = []
    processing_jobs = []
    upload_jobs = []

    for model, sg_name in active_rows:
        logs = model.processing_logs or []
        last_log = logs[-1] if logs else {}
        step = last_log.get("step", "Processing")
        msg = last_log.get("message", "Processing 3D model...")

        job_data = {
            "id": str(model.id),
            "original_filename": model.original_filename,
            "source_group_name": sg_name or f"Group (ID: {model.source_group_id})",
            "telegram_message_id": model.telegram_message_id,
            "file_size_bytes": model.file_size_bytes,
            "processing_status": model.processing_status.value if hasattr(model.processing_status, 'value') else str(model.processing_status),
            "current_step": step,
            "current_message": msg,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            "logs": logs
        }
        active_jobs.append(job_data)

        if "Backup" in step or "Upload" in step:
            upload_jobs.append(job_data)
        else:
            processing_jobs.append(job_data)

    # Query queued models (pending)
    stmt_queued = (
        select(Model3D, SourceGroup.name)
        .outerjoin(SourceGroup, Model3D.source_group_id == SourceGroup.id)
        .where(Model3D.processing_status == ProcessingStatus.pending)
        .order_by(Model3D.created_at.asc())
        .limit(20)
    )
    res_queued = await db.execute(stmt_queued)
    queued_rows = res_queued.all()

    queued_jobs = []
    for model, sg_name in queued_rows:
        queued_jobs.append({
            "id": str(model.id),
            "original_filename": model.original_filename,
            "source_group_name": sg_name or f"Group (ID: {model.source_group_id})",
            "telegram_message_id": model.telegram_message_id,
            "file_size_bytes": model.file_size_bytes,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        })

    # Source groups info for Crawl panel
    stmt_groups = select(SourceGroup).order_by(SourceGroup.id)
    source_groups = (await db.execute(stmt_groups)).scalars().all()
    groups_list = []
    for g in source_groups:
        groups_list.append({
            "id": g.id,
            "chat_id": g.chat_id,
            "name": g.name,
            "model_count": g.model_count,
            "is_active": g.is_active,
            "last_message_id": g.last_message_id
        })

    # Recent target group uploads
    stmt_recent_uploads = (
        select(Model3D, SourceGroup.name)
        .outerjoin(SourceGroup, Model3D.source_group_id == SourceGroup.id)
        .where(
            Model3D.processing_status == ProcessingStatus.completed,
            Model3D.telegram_file_id.isnot(None)
        )
        .order_by(Model3D.updated_at.desc())
        .limit(10)
    )
    recent_uploaded_rows = (await db.execute(stmt_recent_uploads)).all()
    recent_uploads = []
    for model, sg_name in recent_uploaded_rows:
        recent_uploads.append({
            "id": str(model.id),
            "original_filename": model.original_filename,
            "source_group_name": sg_name or "Nguồn Telegram",
            "telegram_file_id": model.telegram_file_id,
            "face_count": model.face_count,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        })

    # Summary count
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    stmt_completed_today = select(func.count(Model3D.id)).where(
        Model3D.processing_status == ProcessingStatus.completed,
        Model3D.updated_at >= today_start
    )

    completed_today_count = (await db.execute(stmt_completed_today)).scalar() or 0

    return {
        "summary": {
            "active_count": len(active_jobs),
            "queued_count": len(queued_jobs),
            "completed_today_count": completed_today_count,
            "avg_processing_time_sec": 18.0
        },
        "queue_info": {
            "queued_jobs": queued_jobs,
            "queued_count": len(queued_jobs),
            "completed_today_count": completed_today_count
        },
        "crawl_info": {
            "status": "Active scanning",
            "source_groups": groups_list,
            "total_groups": len(groups_list)
        },
        "processing_info": {
            "active_processing": processing_jobs,
            "count": len(processing_jobs)
        },
        "target_upload_info": {
            "target_chat_id": target_chat_str or "Chưa cấu hình",
            "active_uploads": upload_jobs,
            "recent_uploads": recent_uploads
        },
        "active_jobs": active_jobs,
        "queued_jobs": queued_jobs
    }


@router.post(
    "/queue/reprocess-failed",
    summary="Re-enqueue all failed or un-uploaded models for reprocessing (admin only)",
)
async def reprocess_failed_models_api(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
):
    """Resets failed models & completed-but-not-uploaded models to pending status and pushes them to Redis queue."""
    from app.worker.queue import get_redis_pool
    from sqlalchemy import or_
    stmt_targets = select(Model3D).where(
        or_(
            Model3D.processing_status == ProcessingStatus.failed,
            Model3D.telegram_file_id.is_(None)
        )
    )
    res = await db.execute(stmt_targets)
    target_models = res.scalars().all()

    if not target_models:
        return {"status": "success", "message": "No failed or un-uploaded models to reprocess", "requeued_count": 0}

    redis = await get_redis_pool()
    requeued_count = 0

    for model in target_models:
        model.processing_status = ProcessingStatus.pending
        model.processing_error = None
        requeued_count += 1
        await redis.enqueue_job(
            'process_telegram_message',
            message_id=model.telegram_message_id,
            chat_id=model.source_group_id
        )

    await db.commit()
    return {
        "status": "success",
        "message": f"Successfully re-queued {requeued_count} models for reprocessing & target group upload",
        "requeued_count": requeued_count
    }


