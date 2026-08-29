import pytest
from app.schemas.model3d import FilterParams
from app.api.models import _build_query

def test_build_query_presupported_and_studio():
    filters = FilterParams(is_presupported=True, studio="Sanix")
    stmt = _build_query(filters)
    stmt_str = str(stmt)
    assert "models_3d.is_presupported" in stmt_str
    assert "models_3d.studio_name" in stmt_str


def test_filter_params_all_and_empty_values():
    filters = FilterParams(
        detail_level="all",
        ai_category="all",
        ai_print_type="all",
        studio="all",
    )
    assert filters.detail_level is None
    assert filters.ai_category is None
    assert filters.ai_print_type is None
    assert filters.studio is None


def test_filter_params_valid_enums():
    from app.models.model3d import DetailLevel, PrintType
    filters = FilterParams(
        detail_level="resin_ready",
        ai_print_type="Resin",
    )
    assert filters.detail_level == DetailLevel.resin_ready
    assert filters.ai_print_type == PrintType.Resin

