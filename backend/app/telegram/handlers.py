import logging
from telethon import events
from sqlalchemy import select
from app.telegram.client import get_telegram_client
from app.worker.queue import get_redis_pool
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.model3d import Model3D

logger = logging.getLogger(__name__)

async def handle_new_message(event):
    if not event.message.document:
        return
    
    file_ext = ""
    file_name = "unknown"
    for attribute in event.message.document.attributes:
        if hasattr(attribute, 'file_name'):
            file_name = attribute.file_name
            file_ext = file_name.split('.')[-1].lower()
            break
            
    if file_ext not in ['stl', 'obj', '3mf', 'pm7m', 'pwscene', 'zip', 'rar']:
        return

    # Check for duplicates in DB before enqueuing
    file_id_str = str(event.message.document.id)
    file_size = event.message.document.size

    async with AsyncSessionLocal() as session:
        stmt_dup = select(Model3D.id).where(
            (Model3D.telegram_message_id == event.message.id) |
            (Model3D.telegram_file_id == file_id_str) |
            ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size))
        )
        existing = await session.execute(stmt_dup)
        if existing.scalars().first():
            logger.info(f"File/message {event.message.id} ({file_name}) already in DB. Skipping duplicate.")
            return


    logger.info(f"Found new 3D file: {event.message.id} ({file_name})")
    
    # Enqueue job for worker
    redis = await get_redis_pool()
    await redis.enqueue_job(
        'process_telegram_message', 
        message_id=event.message.id,
        chat_id=event.chat_id
    )


async def register_handlers():
    client = await get_telegram_client()
    settings = get_settings()
    
    # We could also use SettingsService for chat_ids, but for now fallback to env
    from app.services.settings import SettingsService
    # Try getting from DB first, if not use env.
    chat_ids_str = await SettingsService.get_setting("TELEGRAM_CHAT_IDS")
    
    if chat_ids_str:
        try:
            chat_ids = [int(x.strip()) for x in chat_ids_str.split(',') if x.strip()]
        except ValueError:
            chat_ids = settings.chat_ids
    else:
        chat_ids = settings.chat_ids
        
    client.add_event_handler(
        handle_new_message, 
        events.NewMessage(chats=chat_ids)
    )
