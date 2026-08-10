"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-08-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "viewer", name="userrole", create_type=True),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # ── source_groups ─────────────────────────────────────────────
    op.create_table(
        "source_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("model_count", sa.Integer(), nullable=False),
        sa.Column("last_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )

    # ── tags ──────────────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    # ── models_3d ─────────────────────────────────────────────────
    op.create_table(
        "models_3d",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_extension", sa.String(10), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("telegram_file_id", sa.String(500), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("source_group_id", sa.Integer(), nullable=True),
        sa.Column("telegram_message_text", sa.Text(), nullable=True),
        sa.Column("vertex_count", sa.Integer(), nullable=True),
        sa.Column("face_count", sa.Integer(), nullable=True),
        sa.Column(
            "detail_level",
            sa.Enum(
                "low_poly", "medium_poly", "high_poly", "resin_ready",
                name="detaillevel", create_type=True,
            ),
            nullable=True,
        ),
        sa.Column("bbox_x_mm", sa.Float(), nullable=True),
        sa.Column("bbox_y_mm", sa.Float(), nullable=True),
        sa.Column("bbox_z_mm", sa.Float(), nullable=True),
        sa.Column("volume_mm3", sa.Float(), nullable=True),
        sa.Column("thumbnail_path", sa.String(500), nullable=True),
        sa.Column("predicted_name", sa.String(500), nullable=True),
        sa.Column("ai_category", sa.String(100), nullable=True),
        sa.Column(
            "ai_print_type",
            sa.Enum("FDM", "Resin", "Unknown", name="printtype", create_type=True),
            nullable=True,
        ),
        sa.Column("ai_keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ai_raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum(
                "pending", "processing", "completed", "failed",
                name="processingstatus", create_type=True,
            ),
            nullable=False,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processing_retries", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_group_id"], ["source_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_file_id"),
    )

    # ── model_tags (junction) ─────────────────────────────────────
    op.create_table(
        "model_tags",
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["models_3d.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("model_id", "tag_id"),
    )

    # ── processing_jobs ───────────────────────────────────────────
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum(
                "full_pipeline", "analyze_stl", "thumbnail", "ai_tag",
                name="jobtype", create_type=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", name="jobstatus", create_type=True),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["models_3d.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Custom indexes ─────────────────────────────────────────────
    op.create_index("idx_models_status", "models_3d", ["processing_status"])
    op.create_index("idx_models_detail", "models_3d", ["detail_level"])
    op.create_index("idx_models_group", "models_3d", ["source_group_id"])
    op.create_index(
        "idx_models_created", "models_3d", ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_models_fts",
        "models_3d",
        [sa.text(
            "to_tsvector('english', original_filename || ' ' || COALESCE(telegram_message_text, ''))"
        )],
        postgresql_using="gin",
    )
    op.create_index("idx_tags_slug", "tags", ["slug"])


def downgrade() -> None:
    op.drop_index("idx_tags_slug", table_name="tags")
    op.drop_index("idx_models_fts", table_name="models_3d")
    op.drop_index("idx_models_created", table_name="models_3d")
    op.drop_index("idx_models_group", table_name="models_3d")
    op.drop_index("idx_models_detail", table_name="models_3d")
    op.drop_index("idx_models_status", table_name="models_3d")
    op.drop_table("processing_jobs")
    op.drop_table("model_tags")
    op.drop_table("models_3d")
    op.drop_table("tags")
    op.drop_table("source_groups")
    op.drop_table("users")
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS jobtype")
    op.execute("DROP TYPE IF EXISTS processingstatus")
    op.execute("DROP TYPE IF EXISTS printtype")
    op.execute("DROP TYPE IF EXISTS detaillevel")
    op.execute("DROP TYPE IF EXISTS userrole")
