# backend/tests/test_migration.py
"""
Smoke test: verify alembic migration produces the expected tables.
Requires a running PostgreSQL (set DATABASE_URL env var).
Run with: pytest tests/test_migration.py -v --co to just collect,
or: pytest tests/test_migration.py -v -m integration
"""
import os
import pytest

REQUIRED_TABLES = {
    "users",
    "source_groups",
    "models_3d",
    "tags",
    "model_tags",
    "processing_jobs",
}

REQUIRED_INDEXES = {
    "idx_models_status",
    "idx_models_detail",
    "idx_models_group",
    "idx_models_created",
    "idx_models_fts",
    "idx_tags_slug",
}


@pytest.mark.integration
def test_all_tables_exist():
    """Verify alembic has created all expected tables."""
    import subprocess
    result = subprocess.run(
        [
            "docker", "exec", "stl_postgres",
            "psql", "-U", "stluser", "-d", "stl_library",
            "-c", "SELECT tablename FROM pg_tables WHERE schemaname='public';"
        ],
        capture_output=True, text=True
    )
    output = result.stdout
    for table in REQUIRED_TABLES:
        assert table in output, f"Table '{table}' not found in DB. Output: {output}"


@pytest.mark.integration
def test_all_indexes_exist():
    """Verify all custom indexes were created."""
    import subprocess
    result = subprocess.run(
        [
            "docker", "exec", "stl_postgres",
            "psql", "-U", "stluser", "-d", "stl_library",
            "-c", "SELECT indexname FROM pg_indexes WHERE schemaname='public';"
        ],
        capture_output=True, text=True
    )
    output = result.stdout
    for idx in REQUIRED_INDEXES:
        assert idx in output, f"Index '{idx}' not found. Output: {output}"
