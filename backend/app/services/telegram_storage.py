"""Telegram file streaming service.

Streams STL/OBJ files directly from Telegram to the HTTP client without
writing to disk — satisfying the architecture constraint that no permanent
local file storage is used.
"""
from __future__ import annotations

from typing import AsyncGenerator

# Default chunk size: 512 KB — balances memory use and network efficiency
_CHUNK_SIZE = 512 * 1024  # 512 KB


async def stream_file_from_telegram(
    client,
    file_id: str,
    chunk_size: int = _CHUNK_SIZE,
) -> AsyncGenerator[bytes, None]:
    """Async generator that streams a Telegram file by chunk.

    Args:
        client:     An authenticated Telethon ``TelegramClient`` instance.
        file_id:    The Telegram ``file_id`` string stored in the database.
                    Passed directly to ``client.iter_download()``.
        chunk_size: Size of each yielded byte chunk (default 512 KB).

    Yields:
        Raw bytes chunks suitable for use in a ``StreamingResponse``.
    """
    async for chunk in client.iter_download(file_id, chunk_size=chunk_size):
        yield chunk
