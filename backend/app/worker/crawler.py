import asyncio
import logging
from app.database import AsyncSessionLocal
from app.models.source_group import SourceGroup
from app.models.model3d import Model3D, ProcessingStatus

from sqlalchemy import select
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

async def cron_crawl_history(ctx: dict, **kwargs) -> None:
    """Arq cron job to crawl historical messages from telegram groups."""
    telegram_client = ctx.get("telegram_client")
    if not telegram_client or not telegram_client.is_connected():
        logger.warning("Telegram client not connected. Skipping crawl.")
        return

    from app.services.settings import SettingsService
    import os
    history_days_str = await SettingsService.get_setting("CRAWL_HISTORY_DAYS")
    if not history_days_str:
        history_days_str = os.getenv("CRAWL_HISTORY_DAYS", "30")
        
    if not history_days_str or int(history_days_str) <= 0:
        logger.info("Auto-history crawling disabled (CRAWL_HISTORY_DAYS <= 0).")
        return  # Auto-history crawling is disabled if 0 or not set

    try:
        history_days = min(max(1, int(history_days_str)), 3650)
        target_date = datetime.now(timezone.utc) - timedelta(days=history_days)
    except Exception:
        target_date = datetime.now(timezone.utc) - timedelta(days=365)

    redis = ctx.get("redis")
    
    async with AsyncSessionLocal() as session:
        # Auto-sync source groups from TELEGRAM_CHAT_IDS setting
        from app.services.source_group_sync import sync_source_groups_from_settings
        await sync_source_groups_from_settings(session=session, telegram_client=telegram_client)

        # Fetch active source groups
        stmt = select(SourceGroup).where(SourceGroup.is_active == True)
        result = await session.execute(stmt)
        groups = result.scalars().all()
        
        if not groups:
            return
            
        for group in groups:
            chat_id = group.chat_id
            offset_id = group.oldest_message_id or 0
            group_title = group.name or str(chat_id)
            logger.info(f"[CÀO LỊCH SỬ] 🔍 Đang quét nhóm '{group_title}' (ID: {chat_id}) | Mốc bắt đầu: #{offset_id or 'MỚI NHẤT'}")

            try:
                # ── Kiểm tra nhóm có Forum Topics (Tabs) hay không ──
                entity = None
                try:
                    entity = await telegram_client.get_entity(chat_id)
                except Exception:
                    pass

                is_forum = getattr(entity, 'forum', False) if entity else False
                topics_to_crawl = [(None, "Chung")]

                if is_forum and entity:
                    try:
                        from telethon import functions, types
                        res = await telegram_client(functions.channels.GetForumTopicsRequest(
                            channel=entity,
                            offset_date=None,
                            offset_id=0,
                            offset_topic=0,
                            limit=100
                        ))
                        if res and res.topics:
                            topics_to_crawl = [
                                (t.id, t.title) for t in res.topics 
                                if isinstance(t, types.ForumTopic)
                            ]
                            logger.info(f"[CÀO LỊCH SỬ] 📑 Nhóm '{group_title}' là FORUM với {len(topics_to_crawl)} Tab: {[t[1] for t in topics_to_crawl]}")
                    except Exception as fe:
                        logger.warning(f"Không thể lấy topics của forum {chat_id}: {fe}")

                total_files_queued = 0

                for topic_id, topic_title in topics_to_crawl:
                    topic_label = f" [Tab: {topic_title}]" if topic_id is not None else ""
                    # Quét theo đợt (tối đa 3 đợt x 40 tin = 120 tin/chu kỳ/tab) để cào liên tục
                    max_batches = 3
                    batch_size = 40

                    current_offset = offset_id

                    for b in range(max_batches):
                        kwargs = {"offset_id": current_offset, "limit": batch_size}
                        if topic_id is not None:
                            kwargs["reply_to"] = topic_id

                        messages = await telegram_client.get_messages(chat_id, **kwargs)
                        if not messages:
                            break

                        new_oldest_id = current_offset

                        for message in messages:
                            if new_oldest_id == 0 or message.id < new_oldest_id:
                                new_oldest_id = message.id

                            if not message.document:
                                continue

                            file_ext = ""
                            file_name = "unknown"
                            for attribute in message.document.attributes:
                                if hasattr(attribute, 'file_name'):
                                    file_name = attribute.file_name
                                    file_ext = file_name.split('.')[-1].lower()
                                    break

                            if file_ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar']:
                                file_size_mb = (message.document.size / (1024 * 1024)) if message.document else 0

                                # Check date constraint
                                if message.date and message.date < target_date:
                                    logger.info(f"[CÀO LỊCH SỬ]{topic_label} ⏩ Tin #{message.id} ({file_name}) đã cũ hơn {history_days} ngày. Dừng tab.")
                                    break

                                # Check duplicates in DB
                                file_id_str = str(message.document.id)
                                file_size = message.document.size
                                stmt_dup = select(Model3D).where(
                                    (Model3D.telegram_message_id == message.id) |
                                    (Model3D.telegram_file_id == file_id_str) |
                                    ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size))
                                )
                                existing_res = await session.execute(stmt_dup)
                                existing_m = existing_res.scalars().first()
                                if existing_m:
                                    if existing_m.processing_status == ProcessingStatus.completed and existing_m.telegram_file_id:
                                        continue
                                    elif (existing_m.processing_retries or 0) >= 5:
                                        continue

                                # Đẩy vào hàng đợi Redis để worker bốc ngay và FORWARD LẬP TỨC (0.05s)
                                await redis.enqueue_job(
                                    'process_telegram_message', 
                                    message_id=message.id,
                                    chat_id=chat_id,
                                    _job_timeout=7200
                                )
                                total_files_queued += 1
                                logger.info(f"[CÀO LỊCH SỬ]{topic_label} 🚀 Đã đẩy '{file_name}' (#{message.id}) vào hàng đợi!")

                                await asyncio.sleep(0.1)

                            current_offset = new_oldest_id

                        # Nghỉ nhẹ giữa các batch
                        await asyncio.sleep(0.3)

                    # Lưu mốc tiến độ
                    if not is_forum:
                        group.oldest_message_id = current_offset
                        group.last_message_id = current_offset
                        await session.commit()

                logger.info(f"[CÀO LỊCH SỬ] Hoàn tất quét nhóm '{group_title}', đã xếp hàng {total_files_queued} file 3D mới.")

            except Exception as e:
                logger.error(f"Failed to crawl history for group {chat_id}: {e}")

async def manual_crawl_history(ctx: dict, chat_id: int, limit: int = 1) -> None:
    """Arq task to manually trigger a history crawl for a specific group."""
    telegram_client = ctx.get("telegram_client")
    if not telegram_client or not telegram_client.is_connected():
        logger.warning("Telegram client not connected. Skipping manual crawl.")
        return

    redis = ctx.get("redis")
    
    logger.info(f"Starting MANUAL crawl for group {chat_id}, limit={limit}")
    
    try:
        async with AsyncSessionLocal() as session:
            messages = await telegram_client.get_messages(chat_id, limit=limit * 10) # Fetch more to find enough files
            files_queued = 0
            
            for message in messages:
                if files_queued >= limit:
                    break
                    
                if not message.document:
                    continue
                    
                file_ext = ""
                file_name = "unknown"
                for attribute in message.document.attributes:
                    if hasattr(attribute, 'file_name'):
                        file_name = attribute.file_name
                        file_ext = file_name.split('.')[-1].lower()
                        break
                        
                if file_ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar']:
                    # Check for duplicates
                    file_id_str = str(message.document.id)
                    file_size = message.document.size
                    stmt_dup = select(Model3D.id).where(
                        (Model3D.telegram_message_id == message.id) |
                        (Model3D.telegram_file_id == file_id_str) |
                        ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size))
                    )
                    existing = await session.execute(stmt_dup)
                    if existing.scalars().first():
                        logger.info(f"[MANUAL CRAWL] Duplicate file/message {message.id} ({file_name}) in {chat_id}. Skipping.")
                        continue

                    # Check duplicates in target group first
                    from app.services.settings import SettingsService
                    from app.config import get_settings as _get_settings
                    target_chat_id = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID", _get_settings().TELEGRAM_TARGET_CHAT_ID)
                    if target_chat_id:
                        try:
                            # Search target group for the same filename to avoid duplicate downloads
                            target_msgs = await telegram_client.get_messages(int(target_chat_id), search=file_name, limit=5)
                            if target_msgs:
                                logger.info(f"[MANUAL CRAWL] File '{file_name}' already exists in target group {target_chat_id}. Skipping download.")
                                continue
                        except Exception as e:
                            logger.error(f"Lỗi khi search file trên nhóm đích: {e}")

                    logger.info(f"[MANUAL CRAWL] Found 3D file: {message.id} in {chat_id}")
                    await redis.enqueue_job(
                        'process_telegram_message', 
                        message_id=message.id,
                        chat_id=chat_id,
                    )
                    files_queued += 1
                    # Drip-feed: chờ 2s giữa các lần enqueue để không gửi ồ ạt
                    await asyncio.sleep(2)
                    
            logger.info(f"[MANUAL CRAWL] Finished. Queued {files_queued} files.")
    except Exception as e:
        logger.error(f"[MANUAL CRAWL] Failed for group {chat_id}: {e}")


async def crawl_target_group_history(ctx: dict, limit: int = 500, **kwargs) -> None:
    """
    Scan the TARGET GROUP for existing 3D files and import them into DB.
    Useful for recovering warehouse data when DB is empty or after VPS migration.
    - Files already in DB (by telegram_file_id or filename+size) are skipped.
    - New files are created as Model3D records and enqueued for process_target_message
      (which runs AI tagging WITHOUT re-uploading since the file is already in target).
    """
    telegram_client = ctx.get("telegram_client")
    if not telegram_client or not telegram_client.is_connected():
        logger.warning("[CÀO NHÓM ĐÍCH] Telegram client không kết nối. Bỏ qua.")
        return

    redis = ctx.get("redis")

    from app.services.settings import SettingsService
    from app.config import get_settings

    target_chat_id_str = await SettingsService.get_setting(
        "TELEGRAM_TARGET_CHAT_ID", get_settings().TELEGRAM_TARGET_CHAT_ID
    )
    if not target_chat_id_str:
        logger.error("[CÀO NHÓM ĐÍCH] TELEGRAM_TARGET_CHAT_ID chưa được cài đặt. Hủy.")
        return

    target_chat_id = int(target_chat_id_str)
    logger.info(f"[CÀO NHÓM ĐÍCH] 🔍 Bắt đầu quét nhóm đích ID={target_chat_id}, tối đa {limit} tin nhắn mới nhất.")

    queued = 0
    skipped = 0

    try:
        async with AsyncSessionLocal() as session:
            # 1. Bulk-load all existing signatures into memory sets for ultra-fast O(1) duplicate checks
            res = await session.execute(
                select(
                    Model3D.telegram_file_id,
                    Model3D.telegram_target_message_id,
                    Model3D.original_filename,
                    Model3D.file_size_bytes,
                )
            )
            existing_file_ids = set()
            existing_target_msg_ids = set()
            existing_signatures = set()

            for row in res.all():
                if row[0]:
                    existing_file_ids.add(str(row[0]))
                if row[1]:
                    existing_target_msg_ids.add(int(row[1]))
                if row[2] and row[3]:
                    existing_signatures.add((str(row[2]), int(row[3])))

            logger.info(
                f"[CÀO NHÓM ĐÍCH] ⚡ Đã nạp {len(existing_file_ids)} file IDs hiện có vào RAM để đối soát siêu tốc O(1)."
            )

            # 2. Iterate messages from Telegram at full streaming speed
            count_scanned = 0
            async for message in telegram_client.iter_messages(target_chat_id, limit=limit):
                count_scanned += 1
                if not message.document:
                    continue

                file_name = "unknown"
                file_ext = ""
                for attr in message.document.attributes:
                    if hasattr(attr, "file_name"):
                        file_name = attr.file_name
                        file_ext = file_name.rsplit(".", 1)[-1].lower()
                        break

                if file_ext not in ["stl", "obj", "3mf", "pm7m", "pwscene", "zip", "rar"]:
                    continue

                file_id_str = str(message.document.id)
                file_size = message.document.size

                # In-memory O(1) instant duplicate check (< 0.0001 ms)
                if (
                    message.id in existing_target_msg_ids
                    or file_id_str in existing_file_ids
                    or (file_name, file_size) in existing_signatures
                ):
                    skipped += 1
                    continue

                # New file — enqueue for target-group import processing
                await redis.enqueue_job(
                    "process_target_message",
                    message_id=message.id,
                    chat_id=target_chat_id,
                    _job_timeout=7200,
                )
                queued += 1

                # Mark as seen in memory
                existing_target_msg_ids.add(message.id)
                existing_file_ids.add(file_id_str)
                existing_signatures.add((file_name, file_size))

                if queued % 50 == 0:
                    logger.info(
                        f"[CÀO NHÓM ĐÍCH] 🚀 Đã enqueue {queued} file mới (đã rà {count_scanned}/{limit} tin nhắn, bỏ qua {skipped} trùng)..."
                    )
                    await asyncio.sleep(0.02)  # Yield to event loop

    except Exception as e:
        logger.error(f"[CÀO NHÓM ĐÍCH] Lỗi: {e}", exc_info=True)

    logger.info(
        f"[CÀO NHÓM ĐÍCH] ✅ Hoàn tất. Đã enqueue {queued} file mới, bỏ qua {skipped} file trùng (trên tổng {count_scanned} tin nhắn)."
    )
