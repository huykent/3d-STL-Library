from telethon import TelegramClient
from app.config import get_settings

_client = None

def get_telegram_client() -> TelegramClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = TelegramClient(
            settings.TELEGRAM_SESSION_NAME, 
            settings.TELEGRAM_API_ID, 
            settings.TELEGRAM_API_HASH
        )
    return _client

async def start_telegram_client():
    client = get_telegram_client()
    settings = get_settings()
    # In production, login needs phone/code if session doesn't exist.
    # We will assume session is pre-authenticated for this automated runner.
    await client.start(phone=settings.TELEGRAM_PHONE)

async def stop_telegram_client():
    client = get_telegram_client()
    await client.disconnect()
