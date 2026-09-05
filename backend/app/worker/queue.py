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

from app.worker.crawler import cron_crawl_history, manual_crawl_history, crawl_target_group_history, cron_watchdog_cleanup
from arq import cron
from arq.worker import func

class WorkerSettings:
    functions = [
        func(process_telegram_message, timeout=7200),
        func(process_manual_upload, timeout=7200),
        func(manual_crawl_history, timeout=7200),
        func(process_target_message, timeout=7200),
        func(crawl_target_group_history, timeout=7200),
        func(cron_crawl_history, timeout=7200),
        func(cron_watchdog_cleanup, timeout=300),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    
    # Controlled concurrency to avoid Telegram DC FloodWait rate limits
    max_jobs = 6
    
    # Increase timeout to 2 hours (7200s)
    job_timeout = 7200
    
    cron_jobs = [
        cron(cron_crawl_history, minute=set(range(0, 60, 2))),  # Every 2 minutes
        cron(cron_watchdog_cleanup, minute=set(range(0, 60, 2)))  # Every 2 minutes
    ]
