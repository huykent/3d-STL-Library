"""Tags router: GET /api/tags."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.tag import Tag
from app.schemas.model3d import TagOut

router = APIRouter()


@router.get(
    "",
    response_model=List[TagOut],
    summary="List all tags ordered by usage count",
)
async def list_tags(
    db: AsyncSession = Depends(get_db),
) -> List[TagOut]:
    """Return all tags sorted by usage_count descending."""
    result = await db.execute(
        select(Tag).order_by(Tag.usage_count.desc())
    )
    tags = result.scalars().all()
    return [TagOut.model_validate(t) for t in tags]
