from telethon import TelegramClient
from app.config import get_settings
from app.services.settings import SettingsService

_client = None

async def get_telegram_client() -> TelegramClient:
    global _client
    if _client is None:
        env_settings = get_settings()
        api_id = await SettingsService.get_setting("TELEGRAM_API_ID")
        api_hash = await SettingsService.get_setting("TELEGRAM_API_HASH")
        
        if not api_id or not api_hash:
            raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in DB or .env")
            
        from telethon.sessions import StringSession
        
        session_string = await SettingsService.get_setting("TELEGRAM_SESSION_STRING")
        
        _client = TelegramClient(
            StringSession(session_string or ""), 
            int(api_id), 
            api_hash
        )
    return _client

async def start_telegram_client():
    client = await get_telegram_client()
    await client.connect()
    
    if not await client.is_user_authorized():
        import logging
        logging.getLogger(__name__).warning("Telegram client is NOT authorized. Please login via Admin Settings.")

async def stop_telegram_client():
    global _client
    if _client is not None:
        await _client.disconnect()
        _client = None

async def restart_telegram_client():
    await stop_telegram_client()
    await start_telegram_client()
