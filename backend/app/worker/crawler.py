import asyncio
import logging
from app.database import AsyncSessionLocal
from app.models.source_group import SourceGroup
from app.models.model3d import Model3D, ProcessingStatus

from sqlalchemy import select
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

async def cron_crawl_history(ctx: dict) -> None:
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
            
            # Use offset_id to crawl backwards. If none, start from the latest (0)
            offset_id = group.oldest_message_id or 0
            
            group_title = group.name or str(chat_id)
            logger.info(f"[CÀO LỊCH SỬ] 🔍 Đang quét nhóm '{group_title}' (ID: {chat_id}) | Bắt đầu từ tin nhắn ID: #{offset_id or 'MỚI NHẤT'}")
            
            try:
                # Fetch a small batch of older messages
                messages = await telegram_client.get_messages(chat_id, offset_id=offset_id, limit=20)
                
                found_valid_file = False
                new_oldest_id = offset_id
                
                for message in messages:
                    # Update oldest ID seen
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
                        logger.info(f"[CÀO LỊCH SỬ] 📁 Tìm thấy file 3D #{message.id}: '{file_name}' ({file_size_mb:.1f} MB) trong nhóm '{group_title}'")
                        
                        # Check date constraint
                        if message.date and message.date < target_date:
                            logger.info(f"[CÀO LỊCH SỬ] ⏩ Tin nhắn #{message.id} đã cũ hơn {history_days} ngày. Bỏ qua.")
                        # Check for duplicates (skip if completed or max retries exceeded)

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
                            # Chỉ bỏ qua nếu ĐÃ HOÀN TẤT VÀ ĐÃ UPLOAD LÊN NHÓM ĐÍCH (telegram_file_id is not None)
                            if existing_m.processing_status == ProcessingStatus.completed and existing_m.telegram_file_id:
                                logger.info(f"[CÀO LỊCH SỬ] ⏭️ File '{file_name}' đã có trong nhóm đích (theo DB). Bỏ qua.")
                                continue
                            elif (existing_m.processing_retries or 0) >= 5:
                                logger.info(f"[CÀO LỊCH SỬ] ⏭️ File '{file_name}' đã thử lại quá 5 lần thất bại. Bỏ qua.")
                                continue
                            else:
                                logger.info(f"[CÀO LỊCH SỬ] 🔄 File '{file_name}' chưa có trên nhóm đích. Đẩy vào hàng đợi cào & upload...")
                        else:
                            # DB trống hoặc chưa có, kiểm tra trực tiếp trên Nhóm Đích (để chống trùng khi đổi VPS)
                            from app.config import get_settings
                            target_chat_id_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID", get_settings().TELEGRAM_TARGET_CHAT_ID)
                            if target_chat_id_str:
                                try:
                                    target_chat_id = int(target_chat_id_str)
                                    found_in_target = False
                                    # Tìm kiếm tên file trong nhóm đích
                                    async for tg_msg in telegram_client.iter_messages(target_chat_id, search=file_name, limit=5):
                                        if tg_msg.document and tg_msg.document.size == file_size:
                                            for attr in tg_msg.document.attributes:
                                                if hasattr(attr, 'file_name') and attr.file_name == file_name:
                                                    found_in_target = True
                                                    break
                                        if found_in_target: break
                                        
                                    if found_in_target:
                                        logger.info(f"[CÀO LỊCH SỬ] 🎯 File '{file_name}' đã tồn tại sẵn trên nhóm đích (tìm thấy qua Search). Bỏ qua.")
                                        continue
                                except Exception as e:
                                    logger.error(f"Lỗi khi search file trên nhóm đích: {e}")


                        # Enqueue job
                        await redis.enqueue_job(
                            'process_telegram_message', 
                            message_id=message.id,
                            chat_id=chat_id
                        )
                        logger.info(f"[CÀO LỊCH SỬ] 🚀 Đã đẩy file '{file_name}' (#{message.id}) vào hàng đợi xử lý! (Mốc Msg ID #{new_oldest_id})")
                        found_valid_file = True
                        await asyncio.sleep(1)

                # Save progress so next time we go further back
                if messages:
                    group.oldest_message_id = new_oldest_id
                    group.last_message_id = new_oldest_id
                    await session.commit()
                
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
                    else:
                        from app.config import get_settings
                        from app.services.settings import SettingsService
                        target_chat_id_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID", get_settings().TELEGRAM_TARGET_CHAT_ID)
                        if target_chat_id_str:
                            try:
                                target_chat_id = int(target_chat_id_str)
                                found_in_target = False
                                async for tg_msg in telegram_client.iter_messages(target_chat_id, search=file_name, limit=5):
                                    if tg_msg.document and tg_msg.document.size == file_size:
                                        for attr in tg_msg.document.attributes:
                                            if hasattr(attr, 'file_name') and attr.file_name == file_name:
                                                found_in_target = True
                                                break
                                    if found_in_target: break
                                    
                                if found_in_target:
                                    logger.info(f"[MANUAL CRAWL] 🎯 File '{file_name}' đã tồn tại sẵn trên nhóm đích (tìm thấy qua Search). Bỏ qua.")
                                    continue
                            except Exception as e:
                                logger.error(f"Lỗi khi search file trên nhóm đích: {e}")

                        
                    logger.info(f"[MANUAL CRAWL] Found 3D file: {message.id} in {chat_id}")
                    await redis.enqueue_job(
                        'process_telegram_message', 
                        message_id=message.id,
                        chat_id=chat_id
                    )
                    files_queued += 1
                    # Drip-feed: chờ 2s giữa các lần enqueue để không gửi ồ ạt
                    await asyncio.sleep(2)
                    
            logger.info(f"[MANUAL CRAWL] Finished. Queued {files_queued} files.")
    except Exception as e:
        logger.error(f"[MANUAL CRAWL] Failed for group {chat_id}: {e}")


async def crawl_target_group_history(ctx: dict, limit: int = 500) -> None:
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
