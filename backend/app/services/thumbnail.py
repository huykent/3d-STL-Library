"""Thumbnail renderer for 3D model files.

Uses pyrender for offscreen OpenGL rendering. On Linux VPS/Docker,
set PYOPENGL_PLATFORM=egl before importing pyrender (done here at module level).
On Windows, this is skipped to avoid EGL errors in development.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import numpy as np
import trimesh

logger = logging.getLogger(__name__)

# Set EGL platform for headless Linux rendering BEFORE importing pyrender.
# This is a no-op on Windows (dev machines) where EGL is not available.
if sys.platform != "win32":
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")


def render_thumbnail(
    mesh_path: str,
    output_path: str,
    size: tuple[int, int] = (512, 512),
) -> str:
    """Render an offscreen thumbnail PNG for an STL/OBJ file.

    Args:
        mesh_path: Path to the .stl or .obj file to render.
        output_path: Destination path for the output PNG.
        size: (width, height) in pixels. Default 512×512.

    Returns:
        output_path (same as input, for chaining).

    Raises:
        RuntimeError: If rendering fails.
    """
    import pyrender  # lazy import so EGL env var is set first (Linux)

    # ── Load mesh ────────────────────────────────────────────────
    loaded = trimesh.load(mesh_path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError(f"No geometry in {mesh_path}")
        loaded = trimesh.util.concatenate(list(loaded.geometry.values()))

    mesh: trimesh.Trimesh = loaded  # type: ignore[assignment]

    # ── Centre and normalise mesh ────────────────────────────────
    mesh.apply_translation(-mesh.bounding_box.centroid)
    scale = 1.0 / max(mesh.bounding_box.extents)
    mesh.apply_scale(scale)

    # ── Build pyrender scene ─────────────────────────────────────
    render_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)
    scene = pyrender.Scene(bg_color=[0.12, 0.12, 0.12, 1.0])
    scene.add(render_mesh)

    # Camera — isometric-ish 45° view
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)
    camera_pose = _make_camera_pose(distance=2.5)
    scene.add(camera, pose=camera_pose)

    # Key light from camera direction
    key_light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
    scene.add(key_light, pose=camera_pose)

    # Fill light from opposite-ish angle for depth
    fill_light = pyrender.SpotLight(
        color=[0.6, 0.7, 1.0],
        intensity=2.0,
        innerConeAngle=np.pi / 6.0,
        outerConeAngle=np.pi / 3.0,
    )
    fill_pose = _make_camera_pose(distance=3.0, azimuth=-45.0, elevation=20.0)
    scene.add(fill_light, pose=fill_pose)

    # ── Render ───────────────────────────────────────────────────
    renderer = pyrender.OffscreenRenderer(*size)
    try:
        color, _ = renderer.render(scene)
    finally:
        renderer.delete()

    # ── Save PNG ─────────────────────────────────────────────────
    from PIL import Image

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(color).save(output_path)

    logger.info(f"Thumbnail saved: {output_path}")
    return output_path


def _make_camera_pose(
    distance: float = 2.5,
    azimuth: float = 45.0,
    elevation: float = 30.0,
) -> np.ndarray:
    """Build a 4×4 camera-pose matrix for a given spherical position.

    Args:
        distance: Distance from origin.
        azimuth: Horizontal angle in degrees.
        elevation: Vertical angle in degrees (above horizon).

    Returns:
        4×4 numpy float64 pose matrix (OpenGL convention: -Z forward).
    """
    az = np.radians(azimuth)
    el = np.radians(elevation)

    x = distance * np.cos(el) * np.sin(az)
    y = distance * np.sin(el)
    z = distance * np.cos(el) * np.cos(az)
    eye = np.array([x, y, z])

    target = np.zeros(3)
    up = np.array([0.0, 1.0, 0.0])

    # Gram-Schmidt orthonormalisation
    forward = target - eye
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)
    up_ortho = np.cross(right, forward)

    pose = np.eye(4)
    pose[:3, 0] = right
    pose[:3, 1] = up_ortho
    pose[:3, 2] = -forward  # OpenGL: camera looks down -Z
    pose[:3, 3] = eye
    return pose
