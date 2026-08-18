"""Telegram file streaming service.

Streams STL/OBJ files directly from Telegram to the HTTP client without
writing to disk — satisfying the architecture constraint that no permanent
local file storage is used.
"""
from __future__ import annotations

from typing import AsyncGenerator

import logging
from typing import AsyncGenerator
from telethon import TelegramClient

logger = logging.getLogger(__name__)

# Default chunk size: 2 MB — optimized for high-throughput HTTP streaming
_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB


async def stream_file_from_telegram(
    client: TelegramClient,
    chat_id: int | None = None,
    message_id: int | None = None,
    file_id_fallback: str | None = None,
    chunk_size: int = _CHUNK_SIZE,
) -> AsyncGenerator[bytes, None]:
    """Async generator that streams a Telegram file by chunk.

    Fetches the message document from Telegram and streams raw bytes chunks.
    """
    if not client.is_connected():
        await client.connect()

    # 1. Ưu tiên stream trực tiếp từ Nhóm Đích nếu đã upload (file_id_fallback)
    if file_id_fallback:
        try:
            async for chunk in client.iter_download(file_id_fallback, chunk_size=chunk_size):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"Không thể stream từ target file_id {file_id_fallback}: {e}. Chuyển sang dùng nhóm gốc.")

    # 2. Dự phòng: Stream trực tiếp từ tin nhắn Nhóm Nguồn Telegram gốc
    doc = None
    if chat_id and message_id:
        try:
            msg = await client.get_messages(chat_id, ids=message_id)
            if msg and msg.document:
                doc = msg.document
        except Exception as e:
            logger.warning(f"Could not fetch message {message_id} in {chat_id}: {e}")

    if not doc:
        raise ValueError("Cannot locate Telegram document to stream")

    async for chunk in client.iter_download(doc, chunk_size=chunk_size):
        yield chunk

