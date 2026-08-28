"""STL/OBJ geometry analyzer service.

Uses trimesh to load 3D model files and extract geometry metrics:
- face_count, vertex_count
- detail_level (classified by face count thresholds)
- bounding box dimensions in mm
- volume_mm3 (None for non-watertight meshes)
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

import trimesh


class DetailLevel(str, enum.Enum):
    low_poly = "low_poly"        # < 10,000 faces
    medium_poly = "medium_poly"  # 10,000 – 199,999
    high_poly = "high_poly"      # 200,000 – 999,999
    resin_ready = "resin_ready"  # >= 1,000,000


@dataclass
class MeshAnalysis:
    face_count: int
    vertex_count: int
    detail_level: DetailLevel
    bbox_x_mm: float
    bbox_y_mm: float
    bbox_z_mm: float
    volume_mm3: Optional[float]


def _classify_detail_level(face_count: int) -> DetailLevel:
    """Return detail level enum based on face count thresholds.

    Thresholds (from design spec):
      low_poly   < 10,000
      medium_poly  10,000 – 199,999
      high_poly  200,000 – 999,999
      resin_ready >= 1,000,000
    """
    if face_count < 10_000:
        return DetailLevel.low_poly
    elif face_count < 200_000:
        return DetailLevel.medium_poly
    elif face_count < 1_000_000:
        return DetailLevel.high_poly
    else:
        return DetailLevel.resin_ready


def analyze_mesh(file_path: str) -> MeshAnalysis:
    """Load an STL/OBJ file with trimesh and extract geometry metrics.

    Trimesh loads STL/OBJ into a Trimesh or Scene object.
    For scenes (multi-mesh OBJ), we concatenate into a single mesh.

    Args:
        file_path: Absolute path to the .stl or .obj file.

    Returns:
        MeshAnalysis dataclass with all geometry metrics.

    Raises:
        ValueError: If the file cannot be loaded as a valid mesh.
        FileNotFoundError: If file_path does not exist.
    """
    ext = file_path.split('.')[-1].lower()
    if ext in ['pm7m', 'pwscene']:
        # Proprietary slicer/scene files cannot be parsed by trimesh.
        return MeshAnalysis(
            face_count=0,
            vertex_count=0,
            detail_level=DetailLevel.resin_ready,
            bbox_x_mm=0.0,
            bbox_y_mm=0.0,
            bbox_z_mm=0.0,
            volume_mm3=0.0,
        )

    loaded = trimesh.load(file_path, force="mesh")

    if isinstance(loaded, trimesh.Scene):
        # Multi-mesh OBJ — concatenate into single mesh
        if not loaded.geometry:
            raise ValueError(f"No geometry found in {file_path}")
        loaded = trimesh.util.concatenate(list(loaded.geometry.values()))

    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Could not load {file_path} as a triangular mesh")

    mesh = loaded
    face_count = len(mesh.faces)
    vertex_count = len(mesh.vertices)
    detail_level = _classify_detail_level(face_count)

    # Bounding box in millimetres (trimesh units match file units; STL is typically mm)
    extents = mesh.bounding_box.extents  # [x, y, z] in mesh units
    bbox_x_mm = float(extents[0])
    bbox_y_mm = float(extents[1])
    bbox_z_mm = float(extents[2])

    # Volume (may be None for non-watertight meshes)
    try:
        volume_mm3 = float(mesh.volume) if mesh.is_watertight else None
    except Exception:
        volume_mm3 = None

    return MeshAnalysis(
        face_count=face_count,
        vertex_count=vertex_count,
        detail_level=detail_level,
        bbox_x_mm=bbox_x_mm,
        bbox_y_mm=bbox_y_mm,
        bbox_z_mm=bbox_z_mm,
        volume_mm3=volume_mm3,
    )
