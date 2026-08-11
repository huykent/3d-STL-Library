import asyncio
import os
import sys

# We will run this inside stl_api container
sys.path.append('/app')

from app.database import AsyncSessionLocal
from app.services.settings import SettingsService
from telethon import TelegramClient

async def test_send_code():
    api_id = await SettingsService.get_setting("TELEGRAM_API_ID")
    api_hash = await SettingsService.get_setting("TELEGRAM_API_HASH")
    phone = await SettingsService.get_setting("TELEGRAM_PHONE")
    
    print(f"Testing with: api_id={api_id}, phone={phone}")
    
    if not api_id or not api_hash or not phone:
        print("Missing config!")
        return

    client = TelegramClient('anon_test_session', int(api_id), api_hash)
    await client.connect()
    
    try:
        sent = await client.send_code_request(phone)
        print("Success! Hash:", sent.phone_code_hash)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test_send_code())
