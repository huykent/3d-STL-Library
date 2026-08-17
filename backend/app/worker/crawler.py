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
    history_days_str = await SettingsService.get_setting("CRAWL_HISTORY_DAYS")
    if not history_days_str or int(history_days_str) <= 0:
        return  # Auto-history crawling is disabled if 0 or not set

    history_days = int(history_days_str)
    target_date = datetime.now(timezone.utc) - timedelta(days=history_days)

    redis = ctx.get("redis")
    
    async with AsyncSessionLocal() as session:
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
                            if existing_m.processing_status == ProcessingStatus.completed:
                                logger.info(f"[CÀO LỊCH SỬ] ⏭️ File/tin nhắn #{message.id} ('{file_name}') đã hoàn tất. Bỏ qua.")
                                continue
                            elif (existing_m.processing_retries or 0) >= 3:
                                logger.info(f"[CÀO LỊCH SỬ] ⏭️ File/tin nhắn #{message.id} ('{file_name}') đã thử lại 3 lần thất bại. Bỏ qua.")
                                continue
                            else:
                                logger.info(f"[CÀO LỊCH SỬ] 🔄 File #{message.id} ('{file_name}') từng thất bại (retries: {existing_m.processing_retries}). Thử lại...")


                        # Enqueue job
                        await redis.enqueue_job(
                            'process_telegram_message', 
                            message_id=message.id,
                            chat_id=chat_id
                        )
                        logger.info(f"[CÀO LỊCH SỬ] 🚀 Đã đẩy file '{file_name}' (#{message.id}) vào hàng đợi xử lý! (Tiến độ cào nhóm: mốc ID #{new_oldest_id})")
                        found_valid_file = True
                        # Drip-feed: chờ 2s giữa các lần enqueue để không gửi ồ ạt vào Redis
                        await asyncio.sleep(2)
                        break # Only process 1 file per group per cron run (Drip Feed)

                
                # Save progress so next time we go further back
                if messages:
                    group.oldest_message_id = new_oldest_id
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
