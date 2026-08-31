from arq import create_pool
from arq.connections import RedisSettings
from app.config import get_settings
from app.worker.processor import process_telegram_message, process_manual_upload, process_target_message
from app.core.logging import setup_redis_logging

async def get_redis_pool():
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    return await create_pool(redis_settings)

async def startup(ctx):
    setup_redis_logging("WORKER")
    from app.telegram.client import get_telegram_client
    client = await get_telegram_client()
    await client.connect()
    ctx['telegram_client'] = client
    
    # Init DB models etc if needed
    from app.database import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def shutdown(ctx):
    client = ctx.get('telegram_client')
    if client:
        await client.disconnect()

from app.worker.crawler import cron_crawl_history, manual_crawl_history, crawl_target_group_history
from arq import cron

class WorkerSettings:
    functions = [process_telegram_message, process_manual_upload, manual_crawl_history, process_target_message, crawl_target_group_history]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    
    # Increase concurrent jobs for fast parallel processing
    max_jobs = 20
    
    # Increase timeout to 2 hours (7200s)
    job_timeout = 7200
    
    cron_jobs = [
        cron(cron_crawl_history, minute=set(range(0, 60, 15)))  # Every 15 minutes
    ]
