import pytest
from app.schemas.model3d import FilterParams
from app.api.models import _build_query

def test_build_query_presupported_and_studio():
    filters = FilterParams(is_presupported=True, studio="Sanix")
    stmt = _build_query(filters)
    stmt_str = str(stmt)
    assert "models_3d.is_presupported" in stmt_str
    assert "models_3d.studio_name" in stmt_str
