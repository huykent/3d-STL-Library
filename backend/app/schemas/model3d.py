from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.model3d import DetailLevel, PrintType, ProcessingStatus


class TagOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    slug: str


class Model3DOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    original_filename: str
    file_extension: str
    file_size_bytes: Optional[int]
    is_presupported: bool = False
    studio_name: Optional[str] = None

    # Telegram
    telegram_message_id: Optional[int]
    telegram_target_message_id: Optional[int] = None
    source_group_id: Optional[int]
    telegram_message_text: Optional[str]

    # STL Analysis
    vertex_count: Optional[int]
    face_count: Optional[int]
    part_count: Optional[int]
    detail_level: Optional[DetailLevel]
    bbox_x_mm: Optional[float]
    bbox_y_mm: Optional[float]
    bbox_z_mm: Optional[float]
    volume_mm3: Optional[float]

    # Thumbnail URL (computed by API, not stored)
    thumbnail_url: Optional[str] = None
    image_urls: List[str] = []

    # AI Tagging
    predicted_name: Optional[str]
    ai_category: Optional[str]
    ai_print_type: Optional[PrintType]
    ai_keywords: Optional[List[str]]

    # Status
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    processing_logs: Optional[List[dict]] = None

    # Relations
    tags: List[TagOut] = []

    created_at: datetime
    updated_at: datetime


class Model3DList(BaseModel):
    items: List[Model3DOut]
    total: int
    page: int
    page_size: int
    has_next: bool


class FilterParams(BaseModel):
    """Query parameters for GET /models."""
    search: Optional[str] = None
    detail_level: Optional[DetailLevel] = None
    ai_category: Optional[str] = None
    ai_print_type: Optional[PrintType] = None
    source_group_id: Optional[int] = None
    is_presupported: Optional[bool] = None
    studio: Optional[str] = None
    min_face_count: Optional[int] = None
    max_face_count: Optional[int] = None
    sort_by: Optional[str] = "newest"
    page: int = 1
    page_size: int = 24

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
