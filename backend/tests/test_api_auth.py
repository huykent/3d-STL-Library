"""Tests for POST /api/auth/login endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import Result

from app.models.user import User, UserRole
from app.services.auth_service import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_user(*, is_active: bool = True):
    """Return a MagicMock that quacks like a User ORM instance."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testadmin"
    user.email = "admin@test.com"
    user.password_hash = get_password_hash("secret123")
    user.role = UserRole.admin
    user.is_active = is_active
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def make_mock_db(user_to_return):
    """Build a mock async DB session that returns *user_to_return* on SELECT."""
    mock_result = MagicMock(spec=Result)
    mock_result.scalar_one_or_none.return_value = user_to_return

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ---------------------------------------------------------------------------
# Fixture: ASGI client with overridden DB
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_mock_db():
    """Return the FastAPI app with get_db overridden (no real DB needed)."""
    from app.main import app
    from app.api.deps import get_db

    def _make_client(user_to_return):
        async def fake_get_db():
            yield make_mock_db(user_to_return)

        app.dependency_overrides[get_db] = fake_get_db
        return app

    yield _make_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAuthLogin:
    async def test_login_success(self, app_with_mock_db):
        """Correct credentials → 200 with access_token."""
        app = app_with_mock_db(make_fake_user())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "testadmin", "password": "secret123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, app_with_mock_db):
        """Wrong password → 401."""
        app = app_with_mock_db(make_fake_user())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "testadmin", "password": "wrongpassword"},
            )
        assert response.status_code == 401

    async def test_login_unknown_user(self, app_with_mock_db):
        """Non-existent user (DB returns None) → 401."""
        app = app_with_mock_db(None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "nobody", "password": "doesntmatter"},
            )
        assert response.status_code == 401

    async def test_login_missing_fields(self, app_with_mock_db):
        """Missing body fields → 422 validation error."""
        app = app_with_mock_db(None)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/auth/login", json={})
        assert response.status_code == 422

    async def test_login_inactive_user(self, app_with_mock_db):
        """Inactive user → 401."""
        app = app_with_mock_db(make_fake_user(is_active=False))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": "testadmin", "password": "secret123"},
            )
        assert response.status_code == 401
