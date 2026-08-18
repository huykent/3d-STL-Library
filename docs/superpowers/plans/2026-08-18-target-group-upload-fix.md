# Target Group Upload Fix & Telethon Dialog Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure 100% of processed 3D models are reliably uploaded to the configured Telegram target group/channel by populating Telethon's dialog peer cache and clearing legacy false `telegram_file_id` records in the database.

**Architecture:** Update Telethon startup connection logic in `client.py` to auto-fetch dialogs, update queue management endpoints in `admin.py` to clear legacy non-target file IDs, and refine target upload entity resolution in `processor.py`.

**Tech Stack:** Python 3.12, Telethon, FastAPI, SQLAlchemy async, PostgreSQL, arq, Redis.

## Global Constraints

- Preserve all existing API contracts.
- Do not store permanent STL files locally on VPS.
- Keep all temp files in `/app/temp/{model_id}` cleaned up in `try/finally` blocks.

---

### Task 1: Telethon Peer Entity Dialog Cache Auto-Population

**Files:**
- Modify: `backend/app/telegram/client.py:28-40`

**Interfaces:**
- Consumes: Telethon `TelegramClient.get_dialogs(limit=100)`
- Produces: Warm peer entity cache for `telegram_client.get_entity(target_chat_id)`

- [ ] **Step 1: Update `start_telegram_client()` in `client.py`**

Modify `backend/app/telegram/client.py`:
```python
async def start_telegram_client():
    client = await get_telegram_client()
    await client.connect()
    
    if not await client.is_user_authorized():
        import logging
        logging.getLogger(__name__).warning("Telegram client is NOT authorized. Please login via Admin Settings.")
    else:
        try:
            # Warm up Telethon entity cache for joined target channels and source groups
            await client.get_dialogs(limit=100)
            import logging
            logging.getLogger(__name__).info("Successfully warmed Telethon dialog entity cache.")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to fetch dialogs on client startup: {e}")
```

- [ ] **Step 2: Verify syntax & execution**

Run: `python -c "from app.telegram.client import get_telegram_client; print('Client module valid')"`
Expected: Output `Client module valid`

- [ ] **Step 3: Commit**

```bash
git add backend/app/telegram/client.py
git commit -m "fix(telegram): auto-fetch dialogs on client startup to warm peer entity cache for target group"
```

---

### Task 2: Reset Legacy `telegram_file_id` in Admin API Endpoints

**Files:**
- Modify: `backend/app/api/admin.py:480-530`

**Interfaces:**
- Consumes: PostgreSQL `Model3D` table, `processing_status`
- Produces: API `/api/admin/queue/reprocess-failed` and `/queue/full-recrawl` with clean `telegram_file_id = None` reset for un-uploaded models.

- [ ] **Step 1: Update `reprocess_failed_models_api` and `full_recrawl_queue_api` in `admin.py`**

In `backend/app/api/admin.py`:
```python
@router.post("/queue/reprocess-failed")
async def reprocess_failed_models_api(db: AsyncSession = Depends(get_db)):
    # Reset processing_retries to 0 for failed models
    stmt_failed = select(Model3D).where(Model3D.processing_status == ProcessingStatus.failed)
    failed_models = (await db.execute(stmt_failed)).scalars().all()
    
    for m in failed_models:
        m.processing_status = ProcessingStatus.pending
        m.processing_retries = 0
        m.processing_error = None
        
    # Reset telegram_file_id = None for completed models that were never uploaded to target channel
    stmt_unbacked = select(Model3D).where(
        Model3D.processing_status == ProcessingStatus.completed,
        Model3D.telegram_file_id.isnot(None)
    )
    completed_models = (await db.execute(stmt_unbacked)).scalars().all()
    requeued_count = 0
    
    redis = await get_redis_pool()
    for m in completed_models:
        # If processing_logs does not contain target group upload log, mark as needing upload
        has_upload_log = False
        if m.processing_logs:
            has_upload_log = any("Backup" in str(log) or "upload" in str(log).lower() for log in m.processing_logs)
            
        if not has_upload_log:
            m.telegram_file_id = None
            if m.source_group_id:
                stmt_sg = select(SourceGroup).where(SourceGroup.id == m.source_group_id)
                sg = (await db.execute(stmt_sg)).scalar_one_or_none()
                if sg:
                    await redis.enqueue_job(
                        'process_telegram_message',
                        message_id=m.telegram_message_id,
                        chat_id=sg.chat_id
                    )
                    requeued_count += 1

    await db.commit()
    return {
        "status": "ok", 
        "message": f"Đã reset {len(failed_models)} file lỗi và đẩy lại {requeued_count} file chưa upload sang nhóm đích!",
        "count": len(failed_models) + requeued_count
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/admin.py
git commit -m "fix(admin): reset legacy telegram_file_id for un-uploaded models during queue reprocess"
```

---

### Task 3: Refine Target Upload Resolution and Re-download Fallback in Processor

**Files:**
- Modify: `backend/app/worker/processor.py:500-530`

**Interfaces:**
- Consumes: Telethon client, `download_telegram_document`
- Produces: Reliable Step 6 Target Channel Upload with auto entity resolution fallback

- [ ] **Step 1: Update Target Entity resolution fallback in `processor.py`**

In `backend/app/worker/processor.py`:
```python
                    # Target entity resolution
                    try:
                        target_entity = await telegram_client.get_entity(target_chat_id)
                    except Exception as ge_err:
                        logger.warning(f"Could not resolve Telegram entity for {target_chat_id}: {ge_err}. Fetching dialogs...")
                        try:
                            await telegram_client.get_dialogs(limit=100)
                            target_entity = await telegram_client.get_entity(target_chat_id)
                        except Exception as ge_err2:
                            logger.error(f"Fallback entity resolution failed for {target_chat_id}: {ge_err2}")
                            target_entity = target_chat_id
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/worker/processor.py
git commit -m "fix(processor): add fallback dialog refresh during target group entity resolution"
```
