from __future__ import annotations

from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://stluser:stlpass@postgres:5432/stl_library"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Telegram Userbot
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "stl_crawler"

    # TELEGRAM_CHAT_IDS: stored as a plain str to prevent pydantic-settings from
    # JSON-decoding it before our validator runs. Parsed to List[int] by
    # the field_validator below. Tests access .TELEGRAM_CHAT_IDS and get List[int].
    TELEGRAM_CHAT_IDS: str = ""
    TELEGRAM_TARGET_CHAT_ID: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"

    # JWT
    SECRET_KEY: str = "supersecretkey_change_me_in_production_123456789"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


    # Paths
    THUMBNAIL_DIR: str = "/app/thumbnails"
    TEMP_DIR: str = "/app/temp"

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    @field_validator("TELEGRAM_CHAT_IDS", mode="before")
    @classmethod
    def parse_chat_ids(cls, v: object) -> object:
        """Accept comma-separated string or JSON list string; return as-is for str field."""
        # We keep the field as str but validate it; actual conversion to List[int]
        # happens via the chat_ids property. This validator normalises the raw value.
        if isinstance(v, list):
            # Already a list (e.g. from .env as JSON) — join back to str for storage
            return ",".join(str(x) for x in v)
        return v  # leave as string for the str field

    @property
    def chat_ids(self) -> List[int]:
        """Return TELEGRAM_CHAT_IDS as a list of integers."""
        if not self.TELEGRAM_CHAT_IDS:
            return []
        raw = self.TELEGRAM_CHAT_IDS.strip()
        # Handle JSON array format: "[−100111,−100222]"
        if raw.startswith("["):
            import json
            return [int(x) for x in json.loads(raw)]
        # Comma-separated: "-100111,-100222"
        return [int(x.strip()) for x in raw.split(",") if x.strip()]


def get_settings() -> Settings:
    return Settings()
