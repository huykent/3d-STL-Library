"""Tests for /api/admin endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import Result

from app.models.source_group import SourceGroup
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_user(role: UserRole = UserRole.viewer) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.username = f"user_{role.value}"
    u.email = f"{role.value}@test.com"
    u.role = role
    u.is_active = True
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def make_fake_group(idx: int = 1) -> MagicMock:
    g = MagicMock(spec=SourceGroup)
    g.id = idx
    g.chat_id = -100000 + idx
    g.name = f"Group {idx}"
    g.username = f"group{idx}"
    g.is_active = True
    g.model_count = idx * 5
    g.last_message_id = None
    g.created_at = datetime.now(timezone.utc)
    return g


def make_mock_db(users=None, groups=None):
    mock_session = AsyncMock()

    def execute_side_effect(stmt, *args, **kwargs):
        result = MagicMock(spec=Result)
        result.scalars.return_value.all.return_value = users or groups or []
        result.scalar_one_or_none.return_value = None
        return result

    def add_side_effect(obj):
        """Simulate DB assigning id and defaults after add()."""
        if not getattr(obj, "id", None):
            obj.id = 1
        if not hasattr(obj, "model_count") or obj.model_count is None:
            obj.model_count = 0

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)
    mock_session.add = MagicMock(side_effect=add_side_effect)
    mock_session.flush = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_app():
    """Yield factory: (db_mock, user_role) → patched app."""
    from app.main import app
    from app.api.deps import get_db, get_current_active_user

    def _make(db_mock, user: MagicMock):
        async def fake_get_db():
            yield db_mock

        async def fake_get_user():
            return user

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = fake_get_user
        return app

    yield _make
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: GET /api/admin/users
# ---------------------------------------------------------------------------

class TestAdminUsers:
    async def test_admin_can_list_users(self, admin_app):
        users = [make_fake_user(UserRole.admin), make_fake_user(UserRole.viewer)]
        db = make_mock_db(users=users)
        app = admin_app(db, make_fake_user(UserRole.admin))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/users")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_viewer_gets_403_on_users(self, admin_app):
        db = make_mock_db()
        app = admin_app(db, make_fake_user(UserRole.viewer))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/users")

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: GET /api/admin/groups
# ---------------------------------------------------------------------------

class TestAdminGroups:
    async def test_admin_can_list_groups(self, admin_app):
        groups = [make_fake_group(1), make_fake_group(2)]
        db = make_mock_db(groups=groups)
        app = admin_app(db, make_fake_user(UserRole.admin))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/groups")

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_viewer_gets_403_on_groups(self, admin_app):
        db = make_mock_db()
        app = admin_app(db, make_fake_user(UserRole.viewer))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/groups")

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /api/admin/groups
# ---------------------------------------------------------------------------

class TestAdminCreateGroup:
    async def test_admin_can_create_group(self, admin_app):
        db = make_mock_db()
        app = admin_app(db, make_fake_user(UserRole.admin))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/admin/groups",
                json={"chat_id": -100123456, "name": "New Group"},
            )

        assert response.status_code == 201

    async def test_viewer_gets_403_on_create_group(self, admin_app):
        db = make_mock_db()
        app = admin_app(db, make_fake_user(UserRole.viewer))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/admin/groups",
                json={"chat_id": -100123456, "name": "New Group"},
            )

        assert response.status_code == 403
