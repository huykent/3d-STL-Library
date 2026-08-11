import logging
from telethon import events
from app.telegram.client import get_telegram_client
from app.worker.queue import get_redis_pool
from app.config import get_settings

logger = logging.getLogger(__name__)

async def handle_new_message(event):
    if not event.message.document:
        return
    
    file_ext = ""
    for attribute in event.message.document.attributes:
        if hasattr(attribute, 'file_name'):
            file_ext = attribute.file_name.split('.')[-1].lower()
            break
            
    if file_ext not in ['stl', 'obj', 'zip', 'rar']:
        return

    logger.info(f"Found 3D file: {event.message.id}")
    
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
