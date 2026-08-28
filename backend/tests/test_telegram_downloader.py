import pytest
import os
import zipfile
import shutil
from app.telegram.downloader import extract_3d_files

@pytest.fixture
def dummy_zip_file(tmp_path):
    zip_path = tmp_path / "test_archive.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("model1.stl", b"dummy stl content")
        zf.writestr("model2.obj", b"dummy obj content")
        zf.writestr("readme.txt", b"ignore me")
    yield str(zip_path)
    
@pytest.fixture
def extract_dir(tmp_path):
    yield str(tmp_path / "extracted")

@pytest.mark.asyncio
async def test_extract_3d_files(dummy_zip_file, extract_dir):
    extracted_files = await extract_3d_files(dummy_zip_file, extract_dir)
    
    assert len(extracted_files) == 2
    assert any(f.endswith("model1.stl") for f in extracted_files)
    assert any(f.endswith("model2.obj") for f in extracted_files)
    assert not any(f.endswith("readme.txt") for f in extracted_files)
