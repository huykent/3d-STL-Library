import pytest
import os
import tempfile
import struct
from app.services.stl_analyzer import analyze_mesh, MeshAnalysis, DetailLevel


def create_test_stl_binary(num_triangles: int = 5) -> bytes:
    """Create a minimal valid binary STL file."""
    header = b"\x00" * 80
    count = struct.pack("<I", num_triangles)
    triangle = (
        struct.pack("<fff", 0.0, 0.0, 1.0)   # normal
        + struct.pack("<fff", 0.0, 0.0, 0.0)  # v1
        + struct.pack("<fff", 1.0, 0.0, 0.0)  # v2
        + struct.pack("<fff", 0.0, 1.0, 0.0)  # v3
        + b"\x00\x00"                          # attribute byte count
    )
    return header + count + triangle * num_triangles


def test_analyze_mesh_returns_mesh_analysis():
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(create_test_stl_binary(5))
        tmp_path = f.name
    try:
        result = analyze_mesh(tmp_path)
        assert isinstance(result, MeshAnalysis)
        assert result.face_count == 5
        assert result.vertex_count > 0
        assert result.detail_level == DetailLevel.low_poly
        assert result.bbox_x_mm >= 0
        assert result.bbox_y_mm >= 0
        assert result.bbox_z_mm >= 0
    finally:
        os.unlink(tmp_path)


def test_detail_level_thresholds():
    """Test detail_level is computed correctly based on face_count."""
    from app.services.stl_analyzer import _classify_detail_level
    assert _classify_detail_level(5_000) == DetailLevel.low_poly
    assert _classify_detail_level(10_000) == DetailLevel.medium_poly
    assert _classify_detail_level(150_000) == DetailLevel.medium_poly
    assert _classify_detail_level(200_000) == DetailLevel.high_poly
    assert _classify_detail_level(500_000) == DetailLevel.high_poly
    assert _classify_detail_level(1_000_000) == DetailLevel.resin_ready
    assert _classify_detail_level(2_000_000) == DetailLevel.resin_ready


def test_analyze_mesh_invalid_file():
    """Raises on non-existent file."""
    with pytest.raises(Exception):
        analyze_mesh("/tmp/nonexistent_file_xyz.stl")
