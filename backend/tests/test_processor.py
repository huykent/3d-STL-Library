"""Tests for the arq worker processor (full pipeline).

All external services are mocked:
- Telegram download (download_telegram_document)
- trimesh analysis (analyze_mesh)
- pyrender thumbnail (render_thumbnail)
- Ollama tagging (tag_model)
- SQLAlchemy async DB session (AsyncSessionLocal)

Critical invariant: temp file must be deleted even when the pipeline errors.
"""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch


def _make_db_session_mock(model_obj):
    """Create a mock AsyncSession that returns model_obj from execute()."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = model_obj
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    return mock_session


def _make_model_mock(
    model_id="00000000-0000-0000-0000-000000000001",
    filename="test_model.stl",
    ext="stl",
    status="pending",
):
    """Create a minimal Model3D mock."""
    m = MagicMock()
    m.id = model_id
    m.original_filename = filename
    m.file_extension = ext
    m.processing_status = status
    m.processing_retries = 0
    return m


@pytest.mark.asyncio
async def test_process_telegram_message_full_pipeline():
    """Full pipeline: download → analyze → thumbnail → AI tag → DB commit."""
    from app.services.stl_analyzer import MeshAnalysis, DetailLevel
    from app.services.ai_tagger import AITagResult

    mock_analysis = MeshAnalysis(
        face_count=5000,
        vertex_count=2500,
        detail_level=DetailLevel.low_poly,
        bbox_x_mm=50.0,
        bbox_y_mm=30.0,
        bbox_z_mm=20.0,
        volume_mm3=10000.0,
    )
    mock_tags = AITagResult(
        predicted_name="Test Cube",
        category="Functional",
        print_type="FDM",
        keywords=["cube", "test"],
        raw_response={"choices": [{"message": {"content": "{}"}}]},
    )

    # Real temp file so os.unlink in the processor actually works
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"\x00" * 100)
        tmp_file = f.name

    mock_model = _make_model_mock()
    mock_session = _make_db_session_mock(mock_model)
    mock_telegram_client = AsyncMock()
    mock_telegram_client.get_messages = AsyncMock(return_value=MagicMock())  # fake TG message
    mock_ctx = {"telegram_client": mock_telegram_client}

    with (
        patch("app.worker.processor.download_telegram_document", new_callable=AsyncMock, return_value=tmp_file),
        patch("app.worker.processor.analyze_mesh", return_value=mock_analysis),
        patch("app.worker.processor.render_thumbnail", return_value="/app/thumbnails/test.png"),
        patch("app.worker.processor.tag_model", new_callable=AsyncMock, return_value=mock_tags),
        patch("app.worker.processor.AsyncSessionLocal", return_value=mock_session),
    ):
        from app.worker.processor import process_telegram_message
        await process_telegram_message(mock_ctx, message_id=12345, chat_id=-100123456)

    # Temp file MUST be cleaned up
    assert not os.path.exists(tmp_file), "Temp file was not deleted after successful processing"

    # Model should be updated to completed
    assert mock_model.processing_status.value == "completed" or str(mock_model.processing_status) in ("completed", "ProcessingStatus.completed")


@pytest.mark.asyncio
async def test_process_telegram_message_cleans_up_on_error():
    """Even if analyze_mesh raises, the temp file must be deleted."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"\x00" * 100)
        tmp_file = f.name

    mock_model = _make_model_mock()
    mock_session = _make_db_session_mock(mock_model)
    mock_telegram_client = AsyncMock()
    mock_telegram_client.get_messages = AsyncMock(return_value=MagicMock())
    mock_ctx = {"telegram_client": mock_telegram_client}

    with (
        patch("app.worker.processor.download_telegram_document", new_callable=AsyncMock, return_value=tmp_file),
        patch("app.worker.processor.analyze_mesh", side_effect=RuntimeError("trimesh failed")),
        patch("app.worker.processor.AsyncSessionLocal", return_value=mock_session),
    ):
        from app.worker.processor import process_telegram_message
        # Should NOT raise — errors are caught internally
        await process_telegram_message(mock_ctx, message_id=99999, chat_id=-100123456)

    assert not os.path.exists(tmp_file), "Temp file was not deleted after pipeline error"


@pytest.mark.asyncio
async def test_process_telegram_message_skips_completed_model():
    """If model is already completed, skip re-processing."""
    mock_model = _make_model_mock(status="completed")
    mock_session = _make_db_session_mock(mock_model)
    mock_ctx = {"telegram_client": AsyncMock()}

    with (
        patch("app.worker.processor.download_telegram_document", new_callable=AsyncMock) as mock_dl,
        patch("app.worker.processor.AsyncSessionLocal", return_value=mock_session),
    ):
        from app.worker.processor import process_telegram_message
        await process_telegram_message(mock_ctx, message_id=11111, chat_id=-100123456)

        # download should NOT be called for already-completed models
        mock_dl.assert_not_called()


@pytest.mark.asyncio
async def test_process_telegram_message_skips_missing_model():
    """If no Model3D found for message_id, return early (nothing crashes)."""
    mock_session = _make_db_session_mock(None)  # scalar_one_or_none → None
    mock_ctx = {"telegram_client": AsyncMock()}

    with (
        patch("app.worker.processor.download_telegram_document", new_callable=AsyncMock) as mock_dl,
        patch("app.worker.processor.AsyncSessionLocal", return_value=mock_session),
    ):
        from app.worker.processor import process_telegram_message
        await process_telegram_message(mock_ctx, message_id=22222, chat_id=-100123456)
        mock_dl.assert_not_called()
