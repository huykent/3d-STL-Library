import json
from typing import Dict, Any, Optional

from sqlalchemy import select
from redis.asyncio import Redis

from app.database import AsyncSessionLocal
from app.models.app_config import AppConfig
from app.config import get_settings

class SettingsService:
    """
    Manages dynamic application configurations from the DB.
    Uses Redis to cache settings to reduce DB queries.
    """
    _redis_client: Optional[Redis] = None
    CACHE_KEY = "app:settings"

    @classmethod
    def get_redis(cls) -> Redis:
        if cls._redis_client is None:
            env_settings = get_settings()
            cls._redis_client = Redis.from_url(env_settings.REDIS_URL, decode_responses=True)
        return cls._redis_client

    @classmethod
    async def get_all_settings(cls) -> Dict[str, str]:
        """Fetch all settings, preferring cache, fallback to DB, fallback to .env."""
        redis = cls.get_redis()
        cached = await redis.hgetall(cls.CACHE_KEY)
        
        # Merge with .env defaults
        env_settings = get_settings()
        defaults = {
            "TELEGRAM_API_ID": str(env_settings.TELEGRAM_API_ID) if env_settings.TELEGRAM_API_ID else "",
            "TELEGRAM_API_HASH": env_settings.TELEGRAM_API_HASH or "",
            "TELEGRAM_PHONE": env_settings.TELEGRAM_PHONE or "",
            "OLLAMA_BASE_URL": env_settings.OLLAMA_BASE_URL or "",
        }

        if cached:
            # Overwrite defaults with cached DB values
            defaults.update(cached)
            return defaults

        # Cache miss, load from DB
        db_settings = {}
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AppConfig))
            configs = result.scalars().all()
            for config in configs:
                db_settings[config.key] = config.value

        # Save to cache
        if db_settings:
            await redis.hset(cls.CACHE_KEY, mapping=db_settings)
            
        defaults.update(db_settings)
        return defaults

    @classmethod
    async def get_setting(cls, key: str, default: str = "") -> str:
        """Get a single setting."""
        settings = await cls.get_all_settings()
        return settings.get(key, default)

    @classmethod
    async def update_settings(cls, new_settings: Dict[str, str]):
        """Update settings in DB and invalidate cache."""
        async with AsyncSessionLocal() as session:
            for key, value in new_settings.items():
                result = await session.execute(select(AppConfig).where(AppConfig.key == key))
                config = result.scalar_one_or_none()
                if config:
                    config.value = str(value)
                else:
                    config = AppConfig(key=key, value=str(value), is_secret=("HASH" in key or "API" in key))
                    session.add(config)
            await session.commit()
            
        # Invalidate cache
        redis = cls.get_redis()
        await redis.delete(cls.CACHE_KEY)
