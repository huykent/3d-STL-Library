import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.database import AsyncSessionLocal
from app.models.source_group import SourceGroup
from sqlalchemy import select, text

async def main():
    async with AsyncSessionLocal() as session:
        # Check source groups
        stmt = select(SourceGroup)
        result = await session.execute(stmt)
        groups = result.scalars().all()
        print(f"Total Source Groups: {len(groups)}")
        for g in groups:
            print(f" - {g.name} (chat_id: {g.chat_id}, active: {g.is_active})")
            
        # Check settings in app_configs
        stmt2 = text("SELECT key, value FROM app_configs WHERE key = 'CRAWL_HISTORY_DAYS'")
        result2 = await session.execute(stmt2)
        settings = result2.fetchall()
        print("Settings CRAWL_HISTORY_DAYS:")
        for s in settings:
            print(f" - {s.key}: {s.value}")

if __name__ == "__main__":
    asyncio.run(main())
