import pytest
from app.models.model3d import Model3D
from app.schemas.model3d import Model3DOut

def test_model3d_large_file_and_new_fields():
    ten_gb = 10 * 1024 * 1024 * 1024  # 10,737,418,240 bytes (10GB)
    m = Model3D(
        original_filename="large_diorama.rar",
        file_extension="rar",
        file_size_bytes=ten_gb,
        is_presupported=True,
        studio_name="Sanix",
        telegram_target_message_id=987654321
    )
    assert m.file_size_bytes == ten_gb
    assert m.is_presupported is True
    assert m.studio_name == "Sanix"
    assert m.telegram_target_message_id == 987654321
