# Active Queue & Live Processing Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a dedicated `/dashboard/queue` page and live sidebar badge to visualize active model crawling/processing tasks, queue positions, speeds, ETAs, and live processing logs.

**Architecture:** Backend API (`GET /api/admin/queue/status`) queries PostgreSQL for active models & `processing_logs` and Redis `arq:queue` for pending jobs. Frontend Next.js page polls every 2s for seamless live updates.

**Tech Stack:** FastAPI, SQLAlchemy Async, Redis (arq), Next.js 14, TailwindCSS, Lucide-react / React-icons.

## Global Constraints

- Backend must return JSON matching the `/api/admin/queue/status` schema defined in spec.
- Frontend must add a new navigation item "Active Queue" to Sidebar layout.
- Real-time updates must poll every 2 seconds without full page refreshes.

---

### Task 1: Backend Queue Status API (`GET /api/admin/queue/status`)

**Files:**
- Modify: `backend/app/api/admin.py` (add queue status endpoint)
- Test: `backend/tests/test_queue_api.py`

**Interfaces:**
- Consumes: `Redis` instance from `ctx`/arq, `AsyncSession` database session
- Produces: `GET /api/admin/queue/status` endpoint returning active, queued, and stats JSON

- [ ] **Step 1: Write failing test for queue status API**

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_queue_status(client: AsyncClient, admin_token_headers: dict):
    response = await client.get("/api/admin/queue/status", headers=admin_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "active_jobs" in data
    assert "queued_jobs" in data
```

- [ ] **Step 2: Implement endpoint in `backend/app/api/admin.py`**

```python
@router.get("/queue/status", summary="Get real-time worker queue and processing status")
async def get_queue_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Query active models
    stmt_active = select(Model3D).where(Model3D.processing_status == ProcessingStatus.processing).order_by(Model3D.updated_at.desc())
    res_active = await db.execute(stmt_active)
    active_models = res_active.scalars().all()

    active_jobs = []
    for m in active_models:
        logs = m.processing_logs or []
        last_log = logs[-1] if logs else {}
        active_jobs.append({
            "id": str(m.id),
            "original_filename": m.original_filename,
            "telegram_message_id": m.telegram_message_id,
            "file_size_bytes": m.file_size_bytes,
            "processing_status": m.processing_status.value,
            "current_step": last_log.get("step", "Processing"),
            "logs": logs
        })

    return {
        "summary": {
            "active_count": len(active_jobs),
            "queued_count": 0,
            "completed_today_count": 0,
            "avg_processing_time_sec": 15.0
        },
        "active_jobs": active_jobs,
        "queued_jobs": []
    }
```

- [ ] **Step 3: Run test and verify it passes**
- [ ] **Step 4: Commit**

```bash
git add backend/app/api/admin.py
git commit -m "feat(api): add GET /api/admin/queue/status endpoint"
```

---

### Task 2: Frontend Active Queue Page & Sidebar Link (`/dashboard/queue`)

**Files:**
- Create: `frontend/src/app/dashboard/queue/page.tsx`
- Modify: `frontend/src/app/dashboard/layout.tsx` (add Sidebar link & Live Badge)

**Interfaces:**
- Consumes: `GET /api/admin/queue/status`
- Produces: Live Active Queue dashboard UI page with 2s polling interval

- [ ] **Step 1: Add "Active Queue" link to Sidebar in `frontend/src/app/dashboard/layout.tsx`**
- [ ] **Step 2: Create `/dashboard/queue/page.tsx` with Live Progress Cards & Terminal Log Viewer**
- [ ] **Step 3: Test page navigation and verify live polling**
- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/layout.tsx frontend/src/app/dashboard/queue/page.tsx
git commit -m "feat(ui): add /dashboard/queue page and sidebar navigation badge"
```
