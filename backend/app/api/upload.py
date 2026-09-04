import os
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.api.deps import get_current_active_admin
from app.telegram.client import get_telegram_client
from app.worker.queue import get_redis_pool
from app.services.settings import SettingsService

router = APIRouter()

from fastapi import BackgroundTasks
import logging

import uuid
import shutil
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_active_user
from app.models.model3d import Model3D, ProcessingStatus
from app.schemas.model3d import Model3DOut
from app.config import get_settings

logger = logging.getLogger(__name__)

@router.post(
    "/upload",
    summary="Upload STL/OBJ/ZIP/RAR file manually",
    response_model=Model3DOut,
    status_code=201
)
async def upload_model_api(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user = Depends(get_current_active_user),
):
    """
    Accept a manual upload, save to temp, insert pending DB record, and enqueue for processing.
    """
    settings = get_settings()
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    valid_exts = {'stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar'}
    if file_ext not in valid_exts:
        raise HTTPException(status_code=400, detail=f"Invalid file extension. Allowed: {valid_exts}")

    # 1. Create a placeholder Model3D in DB
    model = Model3D(
        original_filename=file.filename,
        file_extension=file_ext,
        processing_status=ProcessingStatus.pending,
        telegram_file_id=None,
        telegram_message_id=None,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    # 2. Save file to TEMP_DIR with model.id prefix to ensure uniqueness
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    temp_filename = f"manual_{model.id}_{file.filename}"
    temp_filepath = os.path.join(settings.TEMP_DIR, temp_filename)
    
    try:
        with open(temp_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_size = os.path.getsize(temp_filepath)
        model.file_size_bytes = file_size
        await db.commit()
        await db.refresh(model)
        
    except Exception as e:
        model.processing_status = ProcessingStatus.failed
        model.processing_error = f"Upload failed: {str(e)}"
        await db.commit()
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # 3. Enqueue ARQ task
    redis = await get_redis_pool()
    await redis.enqueue_job(
        "process_manual_upload",
        model_id=str(model.id),
        filepath=temp_filepath,
        _job_timeout=7200
    )
    
    # Reload model with tags to avoid MissingGreenletError during model_validate
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Model3D).options(selectinload(Model3D.tags)).where(Model3D.id == model.id)
    )
    loaded_model = result.scalar_one()
    
    out = Model3DOut.model_validate(loaded_model)
    return out


