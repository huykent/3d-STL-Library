"""Tests for GET /api/models and GET /api/tags endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import Result

from app.models.model3d import Model3D, ProcessingStatus
from app.models.user import User, UserRole
from app.services.auth_service import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_model(idx: int = 1) -> MagicMock:
    m = MagicMock(spec=Model3D)
    m.id = uuid.uuid4()
    m.original_filename = f"model_{idx}.stl"
    m.file_extension = "stl"
    m.file_size_bytes = 1024 * idx
    m.telegram_message_id = 1000 + idx
    m.source_group_id = None
    m.telegram_message_text = None
    m.vertex_count = 100
    m.face_count = 200
    m.detail_level = None
    m.bbox_x_mm = 50.0
    m.bbox_y_mm = 60.0
    m.bbox_z_mm = 70.0
    m.volume_mm3 = 180000.0
    m.thumbnail_path = None
    m.predicted_name = f"Widget {idx}"
    m.ai_category = "functional"
    m.ai_print_type = None
    m.ai_keywords = ["widget"]
    m.processing_status = ProcessingStatus.completed
    m.tags = []
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    return m


def make_fake_user_token(role: str = "viewer") -> str:
    return create_access_token(subject="testuser", role=role)


def make_mock_db(scalar_result=None, scalars_result=None, count_result=0):
    """Build a mock DB session."""
    mock_session = AsyncMock()

    def execute_side_effect(stmt, *args, **kwargs):
        result = MagicMock(spec=Result)
        if scalars_result is not None:
            result.scalars.return_value.all.return_value = scalars_result
        result.scalar_one_or_none.return_value = scalar_result
        result.scalar.return_value = count_result
        return result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)
    return mock_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers():
    token = make_fake_user_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app_with_mock_db():
    """Yield a factory: call with (db_mock) → patched app."""
    from app.main import app
    from app.api.deps import get_db, get_current_active_user

    fake_user = MagicMock(spec=User)
    fake_user.username = "testuser"
    fake_user.role = UserRole.viewer
    fake_user.is_active = True

    def _make(db_mock):
        async def fake_get_db():
            yield db_mock

        async def fake_get_user():
            return fake_user

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = fake_get_user
        return app

    yield _make
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Models listing tests
# ---------------------------------------------------------------------------

class TestGetModels:
    async def test_list_models_returns_200(self, app_with_mock_db, auth_headers):
        models = [make_fake_model(1), make_fake_model(2)]
        db = make_mock_db(scalars_result=models, count_result=2)
        app = app_with_mock_db(db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/models", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_models_pagination(self, app_with_mock_db, auth_headers):
        db = make_mock_db(scalars_result=[], count_result=50)
        app = app_with_mock_db(db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/models?page=2&page_size=10", headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["has_next"] is True

    async def test_list_models_requires_auth(self, app_with_mock_db):
        from app.main import app
        from app.api.deps import get_current_active_user
        # Remove user override to test auth
        if get_current_active_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_active_user]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/models")

        assert response.status_code == 401


class TestGetModelById:
    async def test_get_model_found(self, app_with_mock_db, auth_headers):
        fake = make_fake_model(1)
        db = make_mock_db(scalar_result=fake)
        app = app_with_mock_db(db)
        model_id = str(fake.id)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/models/{model_id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == model_id

    async def test_get_model_not_found(self, app_with_mock_db, auth_headers):
        db = make_mock_db(scalar_result=None)
        app = app_with_mock_db(db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/models/{uuid.uuid4()}", headers=auth_headers
            )

        assert response.status_code == 404
