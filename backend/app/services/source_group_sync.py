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
    Ensures all configured chat IDs exist as SourceGroup records and updates real group names from Telegram.
    """
    if telegram_client is None:
        try:
            from app.telegram.client import get_telegram_client
            tc = await get_telegram_client()
            if not tc.is_connected():
                await tc.connect()
            if await tc.is_user_authorized():
                telegram_client = tc
        except Exception as e:
            logger.debug(f"Could not get telegram client in sync_source_groups: {e}")

    # Build title lookup from dialogs if authorized
    dialog_titles = {}
    if telegram_client and telegram_client.is_connected():
        try:
            dialogs = await telegram_client.get_dialogs(limit=200)
            for d in dialogs:
                if d.is_group or d.is_channel:
                    dialog_titles[d.id] = d.name
        except Exception as e:
            logger.debug(f"Could not load dialog titles: {e}")

    chat_ids_str = await SettingsService.get_setting("TELEGRAM_CHAT_IDS")
    if not chat_ids_str:
        chat_ids_str = get_settings().TELEGRAM_CHAT_IDS

    raw_ids = [x.strip() for x in str(chat_ids_str or "").replace('[', '').replace(']', '').split(',') if x.strip()]
    chat_ids = []
    for r in raw_ids:
        try:
            chat_ids.append(int(r))
        except ValueError:
            pass

    async def _do_sync(db):
        existing_res = await db.execute(select(SourceGroup))
        all_groups = existing_res.scalars().all()
        existing_groups = {g.chat_id: g for g in all_groups}

        changed = False

        # 1. Ensure configured chat_ids exist
        for cid in chat_ids:
            group_name = dialog_titles.get(cid)
            if not group_name and telegram_client:
                try:
                    ent = await telegram_client.get_entity(cid)
                    if hasattr(ent, 'title') and ent.title:
                        group_name = ent.title
                except Exception:
                    pass

            if not group_name:
                group_name = f"Group ({cid})"

            if cid not in existing_groups:
                new_group = SourceGroup(
                    chat_id=cid,
                    name=group_name,
                    is_active=True,
                    model_count=0
                )
                db.add(new_group)
                changed = True
                logger.info(f"Auto-created SourceGroup '{group_name}' for chat_id={cid}")

        # 2. Update real names for any existing groups that still have placeholder names
        for g in all_groups:
            real_name = dialog_titles.get(g.chat_id)
            if not real_name and telegram_client:
                try:
                    ent = await telegram_client.get_entity(g.chat_id)
                    if hasattr(ent, 'title') and ent.title:
                        real_name = ent.title
                except Exception:
                    pass

            if real_name and g.name != real_name:
                logger.info(f"Updating SourceGroup {g.chat_id} name from '{g.name}' to '{real_name}'")
                g.name = real_name
                changed = True

        if changed:
            await db.commit()

    if session:
        await _do_sync(session)
    else:
        async with AsyncSessionLocal() as db:
            await _do_sync(db)

