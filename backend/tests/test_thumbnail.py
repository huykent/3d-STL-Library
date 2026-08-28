"""Tests for thumbnail renderer service.

pyrender is mocked entirely — we don't require OpenGL in CI/CD.
The test verifies that render_thumbnail():
  1. Calls the renderer and saves a PNG via PIL
  2. Creates the output directory if it doesn't exist
"""
import os
import sys

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_pyrender(fake_color: np.ndarray):
    """Build a minimal pyrender mock that returns fake_color from render()."""
    mock_pyrender = MagicMock()
    mock_renderer = MagicMock()
    mock_renderer.render.return_value = (
        fake_color,
        np.zeros((512, 512), dtype=np.float32),
    )
    mock_pyrender.OffscreenRenderer.return_value = mock_renderer
    mock_pyrender.Scene.return_value = MagicMock()
    mock_pyrender.Mesh.from_trimesh.return_value = MagicMock()
    mock_pyrender.DirectionalLight.return_value = MagicMock()
    mock_pyrender.SpotLight.return_value = MagicMock()
    mock_pyrender.PerspectiveCamera.return_value = MagicMock()
    mock_pyrender.RenderFlags = MagicMock()
    return mock_pyrender, mock_renderer


def _make_mock_trimesh_mesh():
    """Return a simple mock trimesh.Trimesh with minimal required attributes."""
    mock_mesh = MagicMock()
    mock_mesh.vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
    mock_mesh.faces = np.array([[0, 1, 2]], dtype=np.int32)
    bb = MagicMock()
    bb.centroid = np.zeros(3)
    bb.extents = np.array([1.0, 1.0, 1.0])
    mock_mesh.bounding_box = bb
    mock_mesh.apply_translation = MagicMock()
    mock_mesh.apply_scale = MagicMock()
    return mock_mesh


def test_render_thumbnail_calls_renderer_and_writes_file(tmp_path):
    """render_thumbnail writes a PNG and returns the output path."""
    output_path = str(tmp_path / "test_thumb.png")
    fake_color = np.zeros((512, 512, 3), dtype=np.uint8)
    fake_color[:, :] = [100, 150, 200]

    mock_pyrender, mock_renderer = _make_mock_pyrender(fake_color)
    mock_mesh = _make_mock_trimesh_mesh()

    # Inject pyrender mock into sys.modules before importing the module under test
    with patch.dict("sys.modules", {"pyrender": mock_pyrender}):
        # Remove cached module so it re-imports with our pyrender mock
        sys.modules.pop("app.services.thumbnail", None)
        import app.services.thumbnail as thumb_mod

        # Patch trimesh at the module level so load() returns our fake mesh
        with patch.object(thumb_mod, "trimesh") as mock_trimesh_mod:
            # Make isinstance(loaded, trimesh.Scene) → False
            mock_trimesh_mod.Scene = type("_FakeScene", (), {})
            mock_trimesh_mod.load.return_value = mock_mesh

            result = thumb_mod.render_thumbnail("fake.stl", output_path)

    assert result == output_path
    mock_renderer.render.assert_called_once()
    assert os.path.exists(output_path)


def test_render_thumbnail_creates_output_directory(tmp_path):
    """render_thumbnail creates the output directory if it doesn't exist."""
    output_path = str(tmp_path / "nested" / "subdir" / "model.png")
    fake_color = np.zeros((512, 512, 3), dtype=np.uint8)

    mock_pyrender, mock_renderer = _make_mock_pyrender(fake_color)
    mock_mesh = _make_mock_trimesh_mesh()

    with patch.dict("sys.modules", {"pyrender": mock_pyrender}):
        sys.modules.pop("app.services.thumbnail", None)
        import app.services.thumbnail as thumb_mod

        with patch.object(thumb_mod, "trimesh") as mock_trimesh_mod:
            mock_trimesh_mod.Scene = type("_FakeScene", (), {})
            mock_trimesh_mod.load.return_value = mock_mesh
            thumb_mod.render_thumbnail("fake.stl", output_path)

    assert os.path.exists(os.path.dirname(output_path))
    assert os.path.exists(output_path)
