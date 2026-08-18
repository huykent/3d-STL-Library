import logging
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.source_group import SourceGroup
from app.services.settings import SettingsService
from app.config import get_settings

logger = logging.getLogger(__name__)

async def sync_source_groups_from_settings(session=None, telegram_client=None) -> None:
    """
    Synchronize TELEGRAM_CHAT_IDS from settings into the source_groups DB table.
    Ensures all configured chat IDs exist as SourceGroup records and updates real group names.
    """
    chat_ids_str = await SettingsService.get_setting("TELEGRAM_CHAT_IDS")
    if not chat_ids_str:
        chat_ids_str = get_settings().TELEGRAM_CHAT_IDS

    if not chat_ids_str:
        return

    # Parse chat IDs cleanly
    raw_ids = [x.strip() for x in str(chat_ids_str).replace('[', '').replace(']', '').split(',') if x.strip()]
    chat_ids = []
    for r in raw_ids:
        try:
            chat_ids.append(int(r))
        except ValueError:
            pass

    if not chat_ids:
        return

    async def _do_sync(db):
        existing_res = await db.execute(select(SourceGroup))
        existing_groups = {g.chat_id: g for g in existing_res.scalars().all()}

        created_any = False
        for cid in chat_ids:
            group_name = f"Group ({cid})"
            
            # Fetch real group title from Telegram if client available
            if telegram_client:
                try:
                    entity = await telegram_client.get_entity(cid)
                    if hasattr(entity, 'title') and entity.title:
                        group_name = entity.title
                except Exception as e:
                    logger.debug(f"Could not fetch Telegram entity title for {cid}: {e}")

            if cid not in existing_groups:
                new_group = SourceGroup(
                    chat_id=cid,
                    name=group_name,
                    is_active=True,
                    model_count=0
                )
                db.add(new_group)
                created_any = True
                logger.info(f"Auto-created SourceGroup '{group_name}' for chat_id={cid}")
            else:
                # Update group name if we got a real title
                g = existing_groups[cid]
                if telegram_client and group_name != f"Group ({cid})" and g.name != group_name:
                    g.name = group_name
                    created_any = True

        if created_any:
            await db.commit()

    if session:
        await _do_sync(session)
    else:
        async with AsyncSessionLocal() as db:
            await _do_sync(db)
