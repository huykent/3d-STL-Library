"""Tests for GET /api/tags endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import Result

from app.models.tag import Tag
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_tag(idx: int) -> MagicMock:
    t = MagicMock(spec=Tag)
    t.id = idx
    t.name = f"tag-{idx}"
    t.slug = f"tag-{idx}"
    t.usage_count = idx * 10
    return t


def make_mock_db(tags):
    mock_session = AsyncMock()
    result = MagicMock(spec=Result)
    result.scalars.return_value.all.return_value = tags
    mock_session.execute = AsyncMock(return_value=result)
    return mock_session


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_tags():
    """Yield factory: call with tags list → patched app."""
    from app.main import app
    from app.api.deps import get_db, get_current_active_user

    fake_user = MagicMock(spec=User)
    fake_user.username = "testuser"
    fake_user.role = UserRole.viewer
    fake_user.is_active = True

    def _make(tags):
        async def fake_get_db():
            yield make_mock_db(tags)

        async def fake_get_user():
            return fake_user

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = fake_get_user
        return app

    yield _make
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetTags:
    async def test_list_tags_returns_200(self, app_with_tags):
        tags = [make_fake_tag(i) for i in range(1, 4)]
        app = app_with_tags(tags)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "tag-1"

    async def test_list_tags_empty(self, app_with_tags):
        app = app_with_tags([])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/tags")

        assert response.status_code == 200
        assert response.json() == []
