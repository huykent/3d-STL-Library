"""Turbo Channel Sweeper (Paired Photo + 3D File Mode):

Sweeps a source channel where each 3D model consists of:
  - 1 or more preview photos / render images (posted right before the file)
  - The 3D archive/model file (.stl, .obj, .3mf, .zip, .rar)

For each model:
  1. Detects the 3D file and its preceding preview photo(s)/album.
  2. Forwards both the Photo(s) AND the File together in chronological order to the target channel.
  3. Downloads the preview photo (~100KB, <0.05s) to /app/thumbnails/{model.id}.jpg for the Next.js Web Dashboard.
  4. Stores the model record into PostgreSQL with status 'completed'.
"""
import asyncio
import os
import sys
import logging
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatForwardsRestrictedError
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/turbo_sweeper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("TurboSweeper")

from app.telegram.client import get_telegram_client
from app.database import AsyncSessionLocal
from app.models.model3d import Model3D, ProcessingStatus
from app.models.source_group import SourceGroup
from app.services.settings import SettingsService
from app.config import get_settings

SOURCE_CHAT_ID = -1004479094189 # Kho Dữ Liệu File STL 3D
VALID_EXTENSIONS = {'stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar'}

async def run_turbo_sweeper():
    settings = get_settings()
    logger.info("=" * 65)
    logger.info("🚀 BẮT ĐẦU TURBO SWEEPER (CHẾ ĐỘ GHÉP CẶP: ẢNH PREVIEW + FILE 3D)")
    logger.info("=" * 65)

    client: TelegramClient = await get_telegram_client()
    if not client.is_connected():
        await client.connect()

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

    while True:
        try:
            logger.info(f"🔍 Đang tải lô 50 tin nhắn từ mốc #{current_offset}...")
            messages = await client.get_messages(SOURCE_CHAT_ID, offset_id=current_offset, limit=50)

            if not messages:
                logger.info("🏁 Đã quét hết toàn bộ tin nhắn trong kênh nguồn!")
                break

            # Sắp xếp tin nhắn theo thứ tự thời gian tăng dần để tìm ảnh trước file
            sorted_msgs = sorted(messages, key=lambda m: m.id)

            for doc_msg in sorted_msgs:
                if not doc_msg.document:
                    continue

                file_name = "unknown_model"
                file_ext = ""
                for attr in doc_msg.document.attributes:
                    if hasattr(attr, 'file_name'):
                        file_name = attr.file_name
                        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ""
                        break

                if file_ext not in VALID_EXTENSIONS:
                    continue

                file_size_bytes = doc_msg.document.size
                file_size_mb = file_size_bytes / (1024 * 1024)

                # 1. Kiểm tra trùng lặp trong DB
                async with AsyncSessionLocal() as session:
                    file_id_str = str(doc_msg.document.id)
                    stmt_dup = select(Model3D.id).where(
                        (Model3D.telegram_message_id == doc_msg.id) |
                        (Model3D.telegram_file_id == file_id_str) |
                        ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size_bytes))
                    )
                    existing = (await session.execute(stmt_dup)).scalars().first()
                    if existing:
                        total_skipped += 1
                        continue

                # 2. Tìm tin nhắn ảnh / album ảnh ngay trước file này (ID từ doc_msg.id - 1 lùi dần)
                photo_msgs = []
                try:
                    # Lấy 6 tin nhắn trước doc_msg để tìm ảnh hoặc album
                    candidate_ids = list(range(max(1, doc_msg.id - 6), doc_msg.id))
                    pre_msgs = await client.get_messages(SOURCE_CHAT_ID, ids=candidate_ids)
                    valid_pre = [m for m in pre_msgs if m is not None]
                    valid_pre.sort(key=lambda m: m.id)

                    # Duyệt lùi từ tin nhắn sát doc_msg nhất
                    last_photo_grouped_id = None
                    for m in reversed(valid_pre):
                        if m.photo:
                            if last_photo_grouped_id is None:
                                last_photo_grouped_id = m.grouped_id
                                photo_msgs.insert(0, m)
                            elif m.grouped_id == last_photo_grouped_id and m.grouped_id is not None:
                                photo_msgs.insert(0, m)
                            elif last_photo_grouped_id is None and len(photo_msgs) < 3:
                                photo_msgs.insert(0, m)
                        elif m.document:
                            # Đã gặp file khác -> dừng gom ảnh
                            break
                except Exception as pe:
                    logger.warning(f"Lỗi tìm ảnh kèm tin #{doc_msg.id}: {pe}")

                # 3. Chuẩn bị danh sách forward: [ảnh 1, ảnh 2..., file]
                photo_ids = [p.id for p in photo_msgs]
                all_ids_to_forward = photo_ids + [doc_msg.id]

                forward_success = False
                forwarded_doc_msg = None

                for attempt in range(3):
                    try:
                        fwd_res = await client.forward_messages(
                            target_entity, 
                            all_ids_to_forward, 
                            from_peer=SOURCE_CHAT_ID
                        )
                        if isinstance(fwd_res, list):
                            # Tìm message chứa document trong kết quả trả về
                            for fm in reversed(fwd_res):
                                if fm.document:
                                    forwarded_doc_msg = fm
                                    break
                            if not forwarded_doc_msg and fwd_res:
                                forwarded_doc_msg = fwd_res[-1]
                        else:
                            forwarded_doc_msg = fwd_res

                        forward_success = True
                        break
                    except FloodWaitError as fwe:
                        wait_sec = fwe.seconds + 2
                        logger.warning(f"⏳ FloodWait: Tạm dừng {wait_sec}s theo yêu cầu Telegram...")
                        await asyncio.sleep(wait_sec)
                    except ChatForwardsRestrictedError:
                        logger.error(f"❌ Kênh nguồn cấm chuyển tiếp tin #{doc_msg.id}")
                        break
                    except Exception as fe:
                        logger.error(f"⚠️ Lỗi forward tin #{doc_msg.id} (thử lần {attempt+1}): {fe}")
                        await asyncio.sleep(2)

                if not forward_success or not forwarded_doc_msg:
                    continue

                target_msg_id = forwarded_doc_msg.id
                saved_file_id = str(forwarded_doc_msg.document.id) if forwarded_doc_msg.document else str(doc_msg.document.id)

                # 4. Tải ảnh preview đầu tiên (~100KB) làm thumbnail cho Web Dashboard
                thumb_filenames = []
                if photo_msgs:
                    try:
                        os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
                        thumb_name = f"{doc_msg.id}_preview.jpg"
                        thumb_full = os.path.join(settings.THUMBNAIL_DIR, thumb_name)
                        await client.download_media(photo_msgs[0], file=thumb_full)
                        if os.path.exists(thumb_full) and os.path.getsize(thumb_full) > 0:
                            thumb_filenames.append(thumb_name)
                    except Exception as th_err:
                        logger.warning(f"Không thể tải ảnh thumbnail #{photo_msgs[0].id}: {th_err}")

                # 5. Lưu vào Database (Bọc try/except xử lý trùng lặp an toàn tuyệt đối)
                async with AsyncSessionLocal() as session:
                    try:
                        new_model = Model3D(
                            telegram_file_id=saved_file_id,
                            telegram_message_id=doc_msg.id,
                            telegram_target_message_id=target_msg_id,
                            source_group_id=sg.id if sg else None,
                            original_filename=file_name,
                            file_extension=file_ext,
                            file_size_bytes=file_size_bytes,
                            processing_status=ProcessingStatus.completed,
                            image_paths=thumb_filenames,
                            telegram_message_text=doc_msg.text or (photo_msgs[0].text if photo_msgs else "")
                        )
                        session.add(new_model)
                        await session.commit()
                    except Exception as ie:
                        await session.rollback()
                        stmt_up = select(Model3D).where(
                            (Model3D.telegram_file_id == saved_file_id) |
                            (Model3D.telegram_message_id == doc_msg.id)
                        )
                        exist_m = (await session.execute(stmt_up)).scalars().first()
                        if exist_m:
                            exist_m.telegram_target_message_id = target_msg_id
                            if thumb_filenames and not exist_m.image_paths:
                                exist_m.image_paths = thumb_filenames
                            await session.commit()

                total_forwarded += 1
                logger.info(
                    f"⚡ [#{total_forwarded}] Vợt trọn bộ ({len(photo_ids)} ảnh + File): '{file_name}' ({file_size_mb:.1f} MB) "
                    f"-> Đích Msg #{target_msg_id} (Gốc #{doc_msg.id})"
                )

                # Pacing an toàn chống FloodWait giữa các mô hình (2.5s)
                await asyncio.sleep(2.5)

            # Cập nhật mốc checkpoint lùi dần
            min_id_in_batch = min(m.id for m in messages)
            current_offset = min_id_in_batch

            async with AsyncSessionLocal() as session:
                stmt_sg = select(SourceGroup).where(SourceGroup.chat_id == SOURCE_CHAT_ID)
                db_sg = (await session.execute(stmt_sg)).scalar_one_or_none()
                if db_sg:
                    db_sg.oldest_message_id = current_offset
                    await session.commit()

            logger.info(f"📊 Đã lưu mốc tiến độ: #{current_offset} | Đã vợt: {total_forwarded} mô hình trọn bộ | Bỏ qua: {total_skipped} file trùng.")
            await asyncio.sleep(1.5)

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
