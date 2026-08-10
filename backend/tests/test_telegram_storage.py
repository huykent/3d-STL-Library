"""Tests for telegram_storage streaming service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStreamFileFromTelegram:
    async def test_yields_bytes_from_iter_download(self):
        """Generator must yield all chunks from iter_download."""
        from app.services.telegram_storage import stream_file_from_telegram

        chunk1 = b"chunk_one_"
        chunk2 = b"chunk_two_"
        chunk3 = b"chunk_three"

        # Mock Telethon client with iter_download async generator
        mock_client = MagicMock()

        async def fake_iter_download(file, chunk_size):
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        mock_client.iter_download = fake_iter_download

        collected = b""
        async for chunk in stream_file_from_telegram(mock_client, "file_id_123"):
            collected += chunk

        assert collected == chunk1 + chunk2 + chunk3

    async def test_yields_nothing_for_empty_download(self):
        """Empty iter_download produces no output."""
        from app.services.telegram_storage import stream_file_from_telegram

        mock_client = MagicMock()

        async def fake_iter_download(file, chunk_size):
            return
            yield  # make it an async generator

        mock_client.iter_download = fake_iter_download

        chunks = []
        async for chunk in stream_file_from_telegram(mock_client, "empty_file"):
            chunks.append(chunk)

        assert chunks == []

    async def test_chunk_size_is_reasonable(self):
        """Verify that iter_download is called with a reasonable chunk_size."""
        from app.services.telegram_storage import stream_file_from_telegram

        mock_client = MagicMock()
        received_chunk_size = None

        async def fake_iter_download(file, chunk_size):
            nonlocal received_chunk_size
            received_chunk_size = chunk_size
            yield b"data"

        mock_client.iter_download = fake_iter_download

        async for _ in stream_file_from_telegram(mock_client, "f123"):
            pass

        assert received_chunk_size is not None
        assert received_chunk_size >= 64 * 1024   # at least 64 KB
        assert received_chunk_size <= 4 * 1024 * 1024  # at most 4 MB
