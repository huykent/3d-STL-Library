from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tag import model_tags

if TYPE_CHECKING:
    from app.models.processing_job import ProcessingJob
    from app.models.source_group import SourceGroup
    from app.models.tag import Tag


class DetailLevel(str, enum.Enum):
    low_poly = "low_poly"        # face_count < 10,000
    medium_poly = "medium_poly"  # 10,000 – 200,000
    high_poly = "high_poly"      # 200,000 – 1,000,000
    resin_ready = "resin_ready"  # > 1,000,000


class PrintType(str, enum.Enum):
    FDM = "FDM"
    Resin = "Resin"
    Unknown = "Unknown"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Model3D(Base):
    __tablename__ = "models_3d"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── File info ─────────────────────────────────────────────────
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # ── Telegram storage ──────────────────────────────────────────
    telegram_file_id: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("source_groups.id"), nullable=True
    )
    telegram_message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── STL Analysis ──────────────────────────────────────────────
    vertex_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    face_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail_level: Mapped[Optional[DetailLevel]] = mapped_column(
        SAEnum(DetailLevel, name="detaillevel", create_type=True), nullable=True
    )
    bbox_x_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_z_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_mm3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Thumbnail ─────────────────────────────────────────────────
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ── AI Tagging ────────────────────────────────────────────────
    predicted_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ai_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_print_type: Mapped[Optional[PrintType]] = mapped_column(
        SAEnum(PrintType, name="printtype", create_type=True), nullable=True
    )
    ai_keywords: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )
    ai_raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Processing Status ─────────────────────────────────────────
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, name="processingstatus", create_type=True),
        default=ProcessingStatus.pending,
        nullable=False,
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_retries: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────
    source_group: Mapped[Optional["SourceGroup"]] = relationship(
        "SourceGroup", back_populates="models", lazy="select"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=model_tags, back_populates="models", lazy="select"
    )
    jobs: Mapped[List["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="model", cascade="all, delete-orphan", lazy="select"
    )
