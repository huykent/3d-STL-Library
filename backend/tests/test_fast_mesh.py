import os
import struct
import zipfile
import pytest
from app.services.fast_mesh import parse_stl_header_bytes, inspect_3d_file, FastMeshInfo

def test_parse_stl_header_bytes():
    # 80 bytes header + 4 bytes face count
    raw = b"\x00" * 80 + struct.pack("<I", 98765)
    faces = parse_stl_header_bytes(raw)
    assert faces == 98765

def test_inspect_binary_stl_file(tmp_path):
    stl_file = tmp_path / "huge_10gb_dummy.stl"
    with open(stl_file, "wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", 554433))
    info = inspect_3d_file(str(stl_file))
    assert info.face_count == 554433
    assert info.part_count == 1
    assert info.is_presupported is False
    assert len(info.file_list) == 1

def test_inspect_zip_archive_with_presupported(tmp_path):
    zip_path = tmp_path / "diorama_presupported.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("body_part1.stl", b"dummy")
        z.writestr("body_part2.stl", b"dummy")
        z.writestr("cape_supported.stl", b"dummy")
        z.writestr("read_me.txt", b"dummy text")
    
    info = inspect_3d_file(str(zip_path))
    assert info.part_count == 3  # 3 valid 3D files
    assert info.is_presupported is True
    assert len(info.file_list) == 4
