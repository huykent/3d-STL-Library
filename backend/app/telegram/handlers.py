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

def register_handlers():
    client = get_telegram_client()
    settings = get_settings()
    client.add_event_handler(
        handle_new_message, 
        events.NewMessage(chats=settings.chat_ids)
    )
