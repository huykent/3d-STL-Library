# Technical Design Spec: Target Group Upload Fix & Telethon Dialog Cache

**Date:** 2026-08-18  
**Topic:** Target Group Backup Upload Pipeline Resolution & Entity Caching  

---

## 1. Executive Summary

This design document outlines the resolution for issues preventing 3D model backup uploads from reaching the configured Telegram target channel/group (`TELEGRAM_TARGET_CHAT_ID`).

---

## 2. Root Cause Analysis

1. **Legacy Record `telegram_file_id` Contamination:**
   Prior to commit `a5e8345`, model creation initially assigned `telegram_file_id` to the source document ID. Consequently, existing records in PostgreSQL contain a non-null `telegram_file_id`, causing the worker skip check (`already_uploaded = model.telegram_file_id is not None`) to incorrectly treat un-uploaded models as already completed and uploaded, skipping Step 6 (Target Channel Upload).

2. **Telethon Peer Entity Cache Missing for Negative Chat IDs:**
   When connecting to negative target chat IDs (e.g. `-1004337289624`), Telethon requires the target peer entity to exist in its internal dialog cache. Without fetching user dialogs on client connection, calling `send_file(target_chat_id, ...)` raises `ValueError: Could not find input entity`.

---

## 3. Proposed Changes

### Component 1: Telethon Client Dialog Caching
- **Location:** [client.py](file:///f:/code/3d-STL-Library/backend/app/telegram/client.py)
- **Change:** In `start_telegram_client()`, after authenticating, execute `await client.get_dialogs(limit=100)` to populate Telethon's internal peer entity cache for all target channels and groups.

### Component 2: Legacy Record Reset API
- **Location:** [admin.py](file:///f:/code/3d-STL-Library/backend/app/api/admin.py)
- **Change:** Update `/queue/reprocess-failed` and `/queue/full-recrawl` to reset `telegram_file_id = None` for any model that lacks proof of target channel upload, forcing worker re-evaluation.

### Component 3: Worker Upload Verification & Logging
- **Location:** [processor.py](file:///f:/code/3d-STL-Library/backend/app/worker/processor.py)
- **Change:** Ensure `target_entity` resolution attempts `get_input_entity` and `get_dialogs` if `get_entity` fails, and write explicit status logs to `processing_logs` at 98% and 99% progress stages.

---

## 4. Verification & Testing Plan

1. **Automated Verification:**
   - Execute test scripts to verify `get_dialogs` populates entity cache for target group ID.
   - Run `/api/admin/queue/reprocess-failed` to verify un-uploaded legacy models have `telegram_file_id` reset to `None` and are re-enqueued.

2. **Manual Verification:**
   - Click **"Xoá Hàng Chờ & Cào Lại"** on the dashboard.
   - Observe worker progress transitioning through 98% -> 99% -> 100% and check the target Telegram group for newly created posts containing album photos + 3D file attachments.
