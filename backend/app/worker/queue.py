from arq import create_pool
from arq.connections import RedisSettings
from app.config import get_settings

async def get_redis_pool():
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    return await create_pool(redis_settings)
