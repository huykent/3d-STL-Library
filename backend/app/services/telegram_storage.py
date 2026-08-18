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


async def fast_stream_document(
    client: TelegramClient,
    doc,
    connection_count: int = 6,
) -> AsyncGenerator[bytes, None]:
    """
    High-Speed Direct Telegram HTTP Stream Generator.
    Uses `connection_count` parallel borrowed MTProto senders to fetch chunks ahead,
    enabling 20MB/s - 45MB/s direct streaming for Telegram Premium accounts.
    """
    import asyncio
    import math
    from telethon import utils
    from telethon.tl.functions.upload import GetFileRequest

    total_size = doc.size or 0
    if total_size <= 0:
        return

    part_size = 512 * 1024  # 512 KB per request
    parts_count = math.ceil(total_size / part_size)

    dc_id, location = utils.get_input_location(doc)
    senders = []
    for _ in range(connection_count):
        try:
            s = await client._borrow_sender(dc_id)
            senders.append(s)
        except Exception:
            break

    if not senders:
        async for chunk in client.iter_download(doc, chunk_size=part_size):
            yield chunk
        return

    part_queue = asyncio.Queue()
    for i in range(parts_count):
        part_queue.put_nowait(i)

    results = {}
    results_cond = asyncio.Condition()

    async def worker(sender):
        while not part_queue.empty():
            try:
                part_idx = part_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            offset = part_idx * part_size
            limit = min(part_size, total_size - offset)

            for attempt in range(3):
                try:
                    res = await sender(GetFileRequest(location, offset=offset, limit=limit))
                    if res and hasattr(res, 'bytes') and res.bytes:
                        async with results_cond:
                            results[part_idx] = res.bytes
                            results_cond.notify_all()
                        break
                except Exception:
                    await asyncio.sleep(0.2)

    worker_tasks = [asyncio.create_task(worker(s)) for s in senders]

    try:
        for current_part in range(parts_count):
            async with results_cond:
                while current_part not in results:
                    await results_cond.wait()
                part_bytes = results.pop(current_part)

            yield part_bytes
    finally:
        for t in worker_tasks:
            t.cancel()
        for s in senders:
            try:
                await client._return_sender(s)
            except Exception:
                pass


async def stream_file_from_telegram(
    client: TelegramClient,
    chat_id: int | None = None,
    message_id: int | None = None,
    file_id_fallback: str | None = None,
    chunk_size: int = _CHUNK_SIZE,
) -> AsyncGenerator[bytes, None]:
    """Async generator that streams a Telegram file by chunk with parallel MTProto prefetching."""
    if not client.is_connected():
        await client.connect()

    doc = None
    # 1. Tìm document từ chat_id + message_id hoặc target file_id
    if chat_id and message_id:
        try:
            try:
                entity = await client.get_entity(chat_id)
            except Exception:
                await client.get_dialogs(limit=100)
                entity = await client.get_entity(chat_id)

            msg = await client.get_messages(entity, ids=message_id)
            if msg and msg.document:
                doc = msg.document
        except Exception as e:
            logger.warning(f"Could not fetch message {message_id} in {chat_id}: {e}")

    if doc:
        try:
            async for chunk in fast_stream_document(client, doc, connection_count=6):
                yield chunk
            return
        except Exception as exc:
            logger.warning(f"fast_stream_document failed: {exc}. Fallback to iter_download.")

    # 2. Fallback: iter_download
    if file_id_fallback:
        async for chunk in client.iter_download(file_id_fallback, chunk_size=chunk_size):
            yield chunk
    elif doc:
        async for chunk in client.iter_download(doc, chunk_size=chunk_size):
            yield chunk
    else:
        raise ValueError("Cannot locate Telegram document to stream")

