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


import re
from sqlalchemy import or_, and_

def _parse_search_intent(search_str: str, filters: FilterParams):
    """Extract filter intents embedded in the search query string."""
    if not search_str:
        return search_str, filters.detail_level, filters.ai_category, filters.ai_print_type

    text = search_str.strip()
    detail_level = filters.detail_level
    ai_category = filters.ai_category
    ai_print_type = filters.ai_print_type

    # Extract print type intent if not explicitly set
    if not ai_print_type:
        if re.search(r'\b(fdm)\b', text, re.IGNORECASE):
            ai_print_type = PrintType.FDM
            text = re.sub(r'\b(fdm)\b', '', text, flags=re.IGNORECASE).strip()
        elif re.search(r'\b(resin)\b', text, re.IGNORECASE):
            ai_print_type = PrintType.Resin
            text = re.sub(r'\b(resin)\b', '', text, flags=re.IGNORECASE).strip()

    # Extract detail level intent if not explicitly set
    if not detail_level:
        if re.search(r'\b(low[ _-]?poly)\b', text, re.IGNORECASE):
            detail_level = DetailLevel.low_poly
            text = re.sub(r'\b(low[ _-]?poly)\b', '', text, flags=re.IGNORECASE).strip()
        elif re.search(r'\b(medium[ _-]?poly)\b', text, re.IGNORECASE):
            detail_level = DetailLevel.medium_poly
            text = re.sub(r'\b(medium[ _-]?poly)\b', '', text, flags=re.IGNORECASE).strip()
        elif re.search(r'\b(high[ _-]?poly)\b', text, re.IGNORECASE):
            detail_level = DetailLevel.high_poly
            text = re.sub(r'\b(high[ _-]?poly)\b', '', text, flags=re.IGNORECASE).strip()
        elif re.search(r'\b(resin[ _-]?ready)\b', text, re.IGNORECASE):
            detail_level = DetailLevel.resin_ready
            text = re.sub(r'\b(resin[ _-]?ready)\b', '', text, flags=re.IGNORECASE).strip()

    # Extract category intent if not explicitly set
    if not ai_category:
        categories = ["Functional", "Mechanical", "Figurine", "Prop", "Miniature", "Terrain", "Jewelry", "Art"]
        for cat in categories:
            if re.search(rf'\b({cat})\b', text, re.IGNORECASE):
                ai_category = cat
                text = re.sub(rf'\b({cat})\b', '', text, flags=re.IGNORECASE).strip()
                break

    return text, detail_level, ai_category, ai_print_type


def _build_query(filters: FilterParams):
    """Build a SELECT statement from filter params with smart multi-field search and sorting."""
    parsed_search, detail_level, ai_category, ai_print_type = _parse_search_intent(filters.search, filters)

    stmt = select(Model3D).options(selectinload(Model3D.tags))

    if parsed_search:
        tokens = [t.strip() for t in parsed_search.split() if t.strip()]
        token_conditions = []
        for token in tokens:
            t_pat = f"%{token}%"
            token_cond = or_(
                Model3D.original_filename.ilike(t_pat),
                Model3D.predicted_name.ilike(t_pat),
                Model3D.telegram_message_text.ilike(t_pat),
                Model3D.ai_category.ilike(t_pat),
                func.array_to_string(Model3D.ai_keywords, ' ').ilike(t_pat),
            )
            token_conditions.append(token_cond)
        if token_conditions:
            stmt = stmt.where(and_(*token_conditions))

    if detail_level:
        stmt = stmt.where(Model3D.detail_level == detail_level)
    if ai_category:
        stmt = stmt.where(Model3D.ai_category == ai_category)
    if ai_print_type:
        stmt = stmt.where(Model3D.ai_print_type == ai_print_type)
    if filters.source_group_id:
        stmt = stmt.where(Model3D.source_group_id == filters.source_group_id)
    if filters.min_face_count is not None:
        stmt = stmt.where(Model3D.face_count >= filters.min_face_count)
    if filters.max_face_count is not None:
        stmt = stmt.where(Model3D.face_count <= filters.max_face_count)

    # Sorting
    if filters.sort_by == "faces_desc":
        stmt = stmt.order_by(Model3D.face_count.desc().nullslast())
    elif filters.sort_by == "faces_asc":
        stmt = stmt.order_by(Model3D.face_count.asc().nullslast())
    elif filters.sort_by == "name_asc":
        stmt = stmt.order_by(func.coalesce(Model3D.predicted_name, Model3D.original_filename).asc())
    else:
        stmt = stmt.order_by(Model3D.created_at.desc())

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
    sort_by: Optional[str] = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
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
        sort_by=sort_by,
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
        
        if m.image_paths:
            out.image_urls = [f"/api/models/{m.id}/images/{i}" for i in range(len(m.image_paths))]
        
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
    "/suggestions",
    summary="Get live search autocomplete suggestions",
)
async def get_search_suggestions(
    q: str = Query("", description="Search term for suggestions"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not q or len(q.strip()) < 2:
        return {"models": []}

    term = f"%{q.strip()}%"
    
    stmt = (
        select(Model3D)
        .where(
            or_(
                Model3D.original_filename.ilike(term),
                Model3D.predicted_name.ilike(term),
                func.array_to_string(Model3D.ai_keywords, ' ').ilike(term)
            )
        )
        .order_by(Model3D.created_at.desc())
        .limit(5)
    )
    res = await db.execute(stmt)
    models = res.scalars().all()

    suggestions = []
    for m in models:
        suggestions.append({
            "id": str(m.id),
            "name": m.predicted_name or m.original_filename,
            "ai_category": m.ai_category or "Uncategorized",
            "thumbnail_url": f"/api/models/{m.id}/thumbnail" if m.thumbnail_path else None
        })

    return {"models": suggestions}



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
        
    if model.image_paths:
        out.image_urls = [f"/api/models/{model.id}/images/{i}" for i in range(len(model.image_paths))]
        
    return out


@router.get(
    "/{model_id}/thumbnail",
    summary="Serve the thumbnail image for a model",
    response_class=FileResponse,
)
async def get_thumbnail(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
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
    from app.config import get_settings
    full_path = os.path.join(get_settings().THUMBNAIL_DIR, thumbnail_path)
    
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail file not found")

    return FileResponse(full_path, media_type="image/png")


@router.get(
    "/{model_id}/images/{index}",
    summary="Serve an album image for a model",
    response_class=FileResponse,
)
async def get_album_image(
    model_id: uuid.UUID,
    index: int,
    db: AsyncSession = Depends(get_db),
):
    import os
    result = await db.execute(
        select(Model3D.image_paths).where(Model3D.id == model_id)
    )
    image_paths = result.scalar_one_or_none()
    
    if image_paths is None:
        raise HTTPException(status_code=404, detail="Model not found")
        
    if not image_paths or index < 0 or index >= len(image_paths):
        raise HTTPException(status_code=404, detail="Image not found")
        
    full_path = os.path.join(get_settings().THUMBNAIL_DIR, image_paths[index])
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Image file not found")
        
    return FileResponse(full_path, media_type="image/png")


@router.get(
    "/{model_id}/download",
    summary="Stream the original 3D file directly from Telegram",
)
async def download_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
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
