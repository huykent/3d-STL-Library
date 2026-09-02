"""Turbo Channel Sweeper: Rapidly relays 3D files from a massive source channel

to the target personal library channel and indexes them into PostgreSQL.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatForwardsRestrictedError
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/turbo_sweep.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("TurboSweeper")

from app.telegram.client import get_telegram_client
from app.database import AsyncSessionLocal
from app.models.model3d import Model3D, ProcessingStatus
from app.models.source_group import SourceGroup
from app.services.settings import SettingsService

SOURCE_CHAT_ID = -1004479094189 # Kho Dữ Liệu File STL 3D
VALID_EXTENSIONS = {'stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar'}

async def run_turbo_sweeper():
    logger.info("=" * 60)
    logger.info("🚀 BẮT ĐẦU TIẾN TRÌNH TURBO SWEEPER (VỢT TOÀN BỘ KHO 3D)")
    logger.info("=" * 60)

    client: TelegramClient = await get_telegram_client()
    if not client.is_connected():
        await client.connect()

    # Get target personal channel
    target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID") or "-1004337289624"
    target_chat_id = int(target_chat_str.strip())
    try:
        target_entity = await client.get_entity(target_chat_id)
    except Exception:
        await client.get_dialogs(limit=100)
        target_entity = await client.get_entity(target_chat_id)

    target_title = getattr(target_entity, 'title', str(target_chat_id))
    logger.info(f"🎯 Kênh Đích tiếp nhận: '{target_title}' (ID: {target_chat_id})")

    # Get checkpoint from database
    async with AsyncSessionLocal() as session:
        stmt = select(SourceGroup).where(SourceGroup.chat_id == SOURCE_CHAT_ID)
        sg = (await session.execute(stmt)).scalar_one_or_none()
        current_offset = sg.oldest_message_id if (sg and sg.oldest_message_id) else 506705

    logger.info(f"📍 Bắt đầu quét lùi từ tin nhắn ID: #{current_offset}")

    total_forwarded = 0
    total_skipped = 0
    last_checkpoint_id = current_offset

    while True:
        try:
            logger.info(f"🔍 Đang tải lô 50 tin nhắn tiếp theo từ mốc #{current_offset}...")
            messages = await client.get_messages(SOURCE_CHAT_ID, offset_id=current_offset, limit=50)

            if not messages:
                logger.info("🏁 Đã duyệt hết toàn bộ tin nhắn trong kênh!")
                break

            for msg in messages:
                current_offset = msg.id

                if not msg.document:
                    continue

                # Get filename and extension
                file_name = "unknown_model"
                file_ext = ""
                for attr in msg.document.attributes:
                    if hasattr(attr, 'file_name'):
                        file_name = attr.file_name
                        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ""
                        break

                if file_ext not in VALID_EXTENSIONS:
                    continue

                file_size_bytes = msg.document.size
                file_size_mb = file_size_bytes / (1024 * 1024)

                # Check duplicate in DB
                async with AsyncSessionLocal() as session:
                    file_id_str = str(msg.document.id)
                    stmt_dup = select(Model3D.id).where(
                        (Model3D.telegram_message_id == msg.id) |
                        (Model3D.telegram_file_id == file_id_str) |
                        ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size_bytes))
                    )
                    existing = (await session.execute(stmt_dup)).scalars().first()

                    if existing:
                        total_skipped += 1
                        continue

                    # Forward to target channel
                    forward_success = False
                    for attempt in range(3):
                        try:
                            fwd = await client.forward_messages(target_entity, msg.id, from_peer=SOURCE_CHAT_ID)
                            fwd_doc = fwd[0] if isinstance(fwd, list) else fwd
                            target_msg_id = fwd_doc.id
                            saved_file_id = str(fwd_doc.document.id) if (fwd_doc and fwd_doc.document) else file_id_str
                            forward_success = True
                            break
                        except FloodWaitError as fwe:
                            wait_sec = fwe.seconds + 2
                            logger.warning(f"⏳ FloodWait: Tạm dừng {wait_sec}s theo yêu cầu Telegram...")
                            await asyncio.sleep(wait_sec)
                        except ChatForwardsRestrictedError:
                            logger.error(f"❌ Kênh nguồn cấm chuyển tiếp tin nhắn #{msg.id}")
                            break
                        except Exception as fe:
                            logger.error(f"⚠️ Lỗi forward tin #{msg.id} (thử lần {attempt+1}): {fe}")
                            await asyncio.sleep(2)

                    if not forward_success:
                        continue

                    # Save to DB as completed
                    new_model = Model3D(
                        telegram_file_id=saved_file_id,
                        telegram_message_id=msg.id,
                        telegram_target_message_id=target_msg_id,
                        source_group_id=sg.id if sg else None,
                        original_filename=file_name,
                        file_extension=file_ext,
                        file_size_bytes=file_size_bytes,
                        processing_status=ProcessingStatus.completed,
                        telegram_message_text=msg.text or ""
                    )
                    session.add(new_model)
                    await session.commit()

                    total_forwarded += 1
                    logger.info(
                        f"⚡ [#{total_forwarded}] Vợt thành công: '{file_name}' ({file_size_mb:.1f} MB) "
                        f"-> Đích Msg #{target_msg_id} (Gốc #{msg.id})"
                    )

                    # Pacing: 0.8s between forwards to be completely safe
                    await asyncio.sleep(0.8)

            # Update checkpoint in database
            async with AsyncSessionLocal() as session:
                stmt_sg = select(SourceGroup).where(SourceGroup.chat_id == SOURCE_CHAT_ID)
                db_sg = (await session.execute(stmt_sg)).scalar_one_or_none()
                if db_sg:
                    db_sg.oldest_message_id = current_offset
                    await session.commit()

            logger.info(f"📊 Đã lưu mốc tiến độ: #{current_offset} | Đã vợt: {total_forwarded} file | Bỏ qua: {total_skipped} file trùng.")
            await asyncio.sleep(0.5)

        except FloodWaitError as fwe:
            wait_sec = fwe.seconds + 5
            logger.warning(f"⏳ FloodWait batch: Chờ {wait_sec}s...")
            await asyncio.sleep(wait_sec)
        except Exception as e:
            logger.error(f"💥 Lỗi vòng lặp quét: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_turbo_sweeper())
