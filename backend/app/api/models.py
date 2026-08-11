"""Models router: GET /api/models, /api/models/{id}, /api/models/{id}/thumbnail."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user, get_db
from app.config import get_settings
from app.models.model3d import DetailLevel, Model3D, PrintType
from app.models.user import User
from app.schemas.model3d import FilterParams, Model3DList, Model3DOut

router = APIRouter()


def _build_query(filters: FilterParams):
    """Build a SELECT statement from filter params."""
    stmt = select(Model3D).options(selectinload(Model3D.tags))

    if filters.search:
        term = f"%{filters.search}%"
        stmt = stmt.where(
            Model3D.original_filename.ilike(term)
            | Model3D.predicted_name.ilike(term)
            | Model3D.telegram_message_text.ilike(term)
        )
    if filters.detail_level:
        stmt = stmt.where(Model3D.detail_level == filters.detail_level)
    if filters.ai_category:
        stmt = stmt.where(Model3D.ai_category == filters.ai_category)
    if filters.ai_print_type:
        stmt = stmt.where(Model3D.ai_print_type == filters.ai_print_type)
    if filters.source_group_id:
        stmt = stmt.where(Model3D.source_group_id == filters.source_group_id)
    if filters.min_face_count is not None:
        stmt = stmt.where(Model3D.face_count >= filters.min_face_count)
    if filters.max_face_count is not None:
        stmt = stmt.where(Model3D.face_count <= filters.max_face_count)

    return stmt


@router.get(
    "",
    response_model=Model3DList,
    summary="List 3D models with filtering and pagination",
)
async def list_models(
    search: Optional[str] = Query(None, description="Full-text search in filename, name, message"),
    detail_level: Optional[DetailLevel] = Query(None),
    ai_category: Optional[str] = Query(None),
    ai_print_type: Optional[PrintType] = Query(None),
    source_group_id: Optional[int] = Query(None),
    min_face_count: Optional[int] = Query(None),
    max_face_count: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Model3DList:
    filters = FilterParams(
        search=search,
        detail_level=detail_level,
        ai_category=ai_category,
        ai_print_type=ai_print_type,
        source_group_id=source_group_id,
        min_face_count=min_face_count,
        max_face_count=max_face_count,
        page=page,
        page_size=page_size,
    )

    base_stmt = _build_query(filters)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    total = count_result.scalar() or 0

    # Paginated rows
    paginated = base_stmt.offset(filters.offset).limit(filters.page_size)
    rows_result = await db.execute(paginated)
    models = rows_result.scalars().all()

    settings = get_settings()
    items = []
    for m in models:
        out = Model3DOut.model_validate(m)
        if m.thumbnail_path:
            out.thumbnail_url = f"/api/models/{m.id}/thumbnail"
        items.append(out)

    has_next = (filters.offset + filters.page_size) < total
    return Model3DList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get(
    "/{model_id}",
    response_model=Model3DOut,
    summary="Get a single 3D model by ID",
)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Model3DOut:
    result = await db.execute(
        select(Model3D)
        .where(Model3D.id == model_id)
        .options(selectinload(Model3D.tags))
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    out = Model3DOut.model_validate(model)
    if model.thumbnail_path:
        out.thumbnail_url = f"/api/models/{model.id}/thumbnail"
    return out


@router.get(
    "/{model_id}/thumbnail",
    summary="Serve the thumbnail image for a model",
    response_class=FileResponse,
)
async def get_thumbnail(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Model3D.thumbnail_path).where(Model3D.id == model_id)
    )
    thumbnail_path = result.scalar_one_or_none()

    if thumbnail_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    if not thumbnail_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No thumbnail available")

    import os
    if not os.path.isfile(thumbnail_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail file not found")

    return FileResponse(thumbnail_path, media_type="image/png")


@router.get(
    "/{model_id}/download",
    summary="Stream the original 3D file directly from Telegram",
)
async def download_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Stream the original STL/OBJ file from Telegram without storing it locally."""
    from fastapi.responses import StreamingResponse
    from app.telegram.client import get_telegram_client
    from app.services.telegram_storage import stream_file_from_telegram

    result = await db.execute(
        select(Model3D.telegram_file_id, Model3D.original_filename).where(
            Model3D.id == model_id
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    file_id, filename = row

    client = await get_telegram_client()
    stream = stream_file_from_telegram(client, file_id)

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )

from app.api.deps import get_current_active_admin
from app.models.tag import Tag

@router.put(
    "/{model_id}",
    response_model=Model3DOut,
    summary="Update model metadata and tags (admin only)",
)
async def update_model(
    model_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
) -> Model3DOut:
    result = await db.execute(
        select(Model3D).options(selectinload(Model3D.tags)).where(Model3D.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if "predicted_name" in body:
        val = body["predicted_name"]
        model.predicted_name = val if val != "" else None
    if "ai_category" in body:
        val = body["ai_category"]
        model.ai_category = val if val != "" else None
    if "ai_print_type" in body:
        val = body["ai_print_type"]
        if val == "":
            model.ai_print_type = None
        else:
            try:
                model.ai_print_type = PrintType(val)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid print type: {val}")

    # Handle tag updates
    if "keywords" in body:
        tag_names = [t.strip().lower() for t in body["keywords"] if t.strip()]
        existing_tags_query = await db.execute(select(Tag).where(Tag.name.in_(tag_names)))
        existing_tags = existing_tags_query.scalars().all()
        existing_tag_map = {t.name: t for t in existing_tags}

        new_tags = []
        for name in tag_names:
            if name in existing_tag_map:
                new_tags.append(existing_tag_map[name])
            else:
                import re
                slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                new_tag = Tag(name=name, slug=slug)
                db.add(new_tag)
                new_tags.append(new_tag)
        
        model.tags = new_tags

    await db.commit()
    await db.refresh(model)
    
    out = Model3DOut.model_validate(model)
    if model.thumbnail_path:
        out.thumbnail_url = f"/api/models/{model.id}/thumbnail"
    return out

@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a model (admin only)",
)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_active_admin),
):
    result = await db.execute(select(Model3D).where(Model3D.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Delete thumbnail if exists
    if model.thumbnail_path:
        import os
        thumb_path = os.path.join(get_settings().THUMBNAIL_DIR, model.thumbnail_path)
        if os.path.exists(thumb_path):
            try:
                os.unlink(thumb_path)
            except Exception:
                pass
                
    await db.delete(model)
    await db.commit()
