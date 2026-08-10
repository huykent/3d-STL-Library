import uuid
import pytest


def test_user_model_importable():
    from app.models.user import User, UserRole
    assert UserRole.admin == "admin"
    assert UserRole.viewer == "viewer"


def test_user_model_columns():
    from app.models.user import User
    cols = {c.name for c in User.__table__.columns}
    assert cols == {
        "id", "username", "email", "password_hash",
        "role", "is_active", "created_at", "updated_at"
    }


def test_user_model_id_is_uuid():
    from app.models.user import User
    from sqlalchemy.dialects.postgresql import UUID
    id_col = User.__table__.columns["id"]
    assert isinstance(id_col.type, UUID)
    assert id_col.primary_key is True


def test_source_group_model_columns():
    from app.models.source_group import SourceGroup
    cols = {c.name for c in SourceGroup.__table__.columns}
    assert cols == {
        "id", "chat_id", "name", "username",
        "is_active", "model_count", "last_message_id", "created_at"
    }


def test_source_group_chat_id_is_bigint():
    from app.models.source_group import SourceGroup
    from sqlalchemy import BigInteger
    col = SourceGroup.__table__.columns["chat_id"]
    assert isinstance(col.type, BigInteger)
    assert col.unique is True


def test_model3d_columns():
    from app.models.model3d import Model3D
    cols = {c.name for c in Model3D.__table__.columns}
    expected = {
        "id", "original_filename", "file_extension", "file_size_bytes",
        "telegram_file_id", "telegram_message_id", "source_group_id",
        "telegram_message_text", "vertex_count", "face_count", "detail_level",
        "bbox_x_mm", "bbox_y_mm", "bbox_z_mm", "volume_mm3",
        "thumbnail_path", "predicted_name", "ai_category", "ai_print_type",
        "ai_keywords", "ai_raw_response", "processing_status",
        "processing_error", "processing_retries", "created_at", "updated_at"
    }
    assert cols == expected


def test_model3d_telegram_file_id_is_unique():
    from app.models.model3d import Model3D
    col = Model3D.__table__.columns["telegram_file_id"]
    assert col.unique is True
    assert col.nullable is False


def test_detail_level_enum_values():
    from app.models.model3d import DetailLevel
    assert DetailLevel.low_poly == "low_poly"
    assert DetailLevel.medium_poly == "medium_poly"
    assert DetailLevel.high_poly == "high_poly"
    assert DetailLevel.resin_ready == "resin_ready"


def test_processing_status_enum_values():
    from app.models.model3d import ProcessingStatus
    assert ProcessingStatus.pending == "pending"
    assert ProcessingStatus.processing == "processing"
    assert ProcessingStatus.completed == "completed"
    assert ProcessingStatus.failed == "failed"


def test_tag_model_columns():
    from app.models.tag import Tag
    cols = {c.name for c in Tag.__table__.columns}
    assert cols == {"id", "name", "slug", "usage_count", "created_at"}


def test_model_tags_junction_columns():
    from app.models.tag import model_tags
    cols = {c.name for c in model_tags.columns}
    assert cols == {"model_id", "tag_id"}


def test_processing_job_columns():
    from app.models.processing_job import ProcessingJob
    cols = {c.name for c in ProcessingJob.__table__.columns}
    assert cols == {
        "id", "model_id", "job_type", "status",
        "error_message", "worker_id",
        "started_at", "completed_at", "created_at"
    }


def test_all_models_importable_from_init():
    from app.models import (
        User, SourceGroup, Tag, Model3D, ProcessingJob,
        UserRole, DetailLevel, PrintType, ProcessingStatus,
        JobType, JobStatus, model_tags, Base
    )
    # SQLAlchemy Table objects raise TypeError on bool(), so check identity not truthiness
    assert User is not None
    assert SourceGroup is not None
    assert Tag is not None
    assert Model3D is not None
    assert ProcessingJob is not None
    assert UserRole is not None
    assert DetailLevel is not None
    assert PrintType is not None
    assert ProcessingStatus is not None
    assert JobType is not None
    assert JobStatus is not None
    assert model_tags is not None  # Table object — don't use bool()
    assert Base is not None
