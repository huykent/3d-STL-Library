import logging
from app.database import AsyncSessionLocal
from app.models.source_group import SourceGroup
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def cron_crawl_history(ctx: dict) -> None:
    """Arq cron job to crawl historical messages from telegram groups."""
    telegram_client = ctx.get("telegram_client")
    if not telegram_client or not telegram_client.is_connected():
        logger.warning("Telegram client not connected. Skipping crawl.")
        return

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
            
            logger.info(f"Crawling history for group {chat_id}, offset_id={offset_id}")
            
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
                    for attribute in message.document.attributes:
                        if hasattr(attribute, 'file_name'):
                            file_ext = attribute.file_name.split('.')[-1].lower()
                            break
                            
                    if file_ext in ['stl', 'obj', 'zip', 'rar']:
                        logger.info(f"Found historical 3D file: {message.id} in {chat_id}")
                        # Enqueue job
                        await redis.enqueue_job(
                            'process_telegram_message', 
                            message_id=message.id,
                            chat_id=chat_id
                        )
                        found_valid_file = True
                        break # Only process 1 file per group per cron run (Drip Feed)
                
                # Save progress so next time we go further back
                if messages:
                    group.oldest_message_id = new_oldest_id
                    await session.commit()
                
            except Exception as e:
                logger.error(f"Failed to crawl history for group {chat_id}: {e}")
