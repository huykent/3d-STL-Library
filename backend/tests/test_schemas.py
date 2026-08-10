import uuid
from datetime import datetime


def test_login_request_schema():
    from app.schemas.auth import LoginRequest
    req = LoginRequest(username="admin", password="password123")
    assert req.username == "admin"
    assert req.password == "password123"


def test_token_response_default_type():
    from app.schemas.auth import TokenResponse
    r = TokenResponse(access_token="abc", refresh_token="xyz")
    assert r.token_type == "bearer"


def test_user_create_lowercases_username():
    from app.schemas.user import UserCreate
    u = UserCreate(username="Admin", email="admin@example.com", password="password123")
    assert u.username == "admin"


def test_user_create_rejects_short_password():
    from app.schemas.user import UserCreate
    import pytest
    with pytest.raises(Exception):
        UserCreate(username="x", email="x@x.com", password="short")


def test_filter_params_offset():
    from app.schemas.model3d import FilterParams
    fp = FilterParams(page=3, page_size=24)
    assert fp.offset == 48  # (3-1) * 24


def test_model3d_list_schema():
    from app.schemas.model3d import Model3DList
    lst = Model3DList(items=[], total=0, page=1, page_size=24, has_next=False)
    assert lst.total == 0
