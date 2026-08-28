# Lightweight Pipeline, 10GB Large File Support & Enhanced UI/UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the 3D STL Library into an ultra-lightweight relay system supporting files up to 10GB & multi-part archives with instant header parsing (<0.001s), zero-disk cloud relay, pre-supported & studio detection, clean Telegram album formatting, and enhanced web dashboard UI.

**Architecture:** 
- Use remote partial MTProto stream download (download only first 1KB of STL for face count) and direct cloud relay for zero-disk VPS forwarding.
- Replace heavy `trimesh`/`pyrender` with a zero-RAM binary header reader and archive inspector.
- Support multi-part archive grouping and 64-bit BigInteger file sizes for 10GB+ collections.
- Package Telegram publications into cohesive albums + styled captions with inline buttons.
- Update frontend to intelligently format sizes (MB/GB), multi-part badges, and handle archives vs single STL meshes.

**Tech Stack:** Python 3.12, FastAPI (StreamingResponse), SQLAlchemy (async, BigInteger), Telethon (MTProto iter_download & send_file), Next.js 14, React, TailwindCSS, Three.js.

## Global Constraints
- Zero heavy CPU/RAM mesh rendering on VPS (no trimesh/pyrender in runtime pipeline).
- All temporary directories MUST be unconditionally deleted in `try ... finally` blocks.
- Files up to 10GB handled with streaming chunk buffers (< 1MB in RAM).

---

### Task 1: Database Model & BigInteger Schema Migration

**Files:**
- Modify: `backend/app/models/model3d.py`
- Modify: `backend/app/schemas/model3d.py`
- Test: `backend/tests/test_model_schema.py`

**Interfaces:**
- Consumes: SQLAlchemy base model
- Produces: `Model3D` with `file_size_bytes: BigInteger` (supports 10GB+), `is_presupported: bool`, `studio_name: str | None`, `telegram_target_message_id: int | None`

- [ ] **Step 1: Write test for 10GB file size and new model attributes**

```python
# backend/tests/test_model_schema.py
import pytest
from app.models.model3d import Model3D

def test_model3d_large_file_and_new_fields():
    ten_gb = 10 * 1024 * 1024 * 1024 # 10,737,418,240 bytes
    m = Model3D(
        original_filename="large_diorama.rar",
        file_extension="rar",
        file_size_bytes=ten_gb,
        is_presupported=True,
        studio_name="Sanix",
        telegram_target_message_id=987654321
    )
    assert m.file_size_bytes == ten_gb
    assert m.is_presupported is True
    assert m.studio_name == "Sanix"
```

- [ ] **Step 2: Run test to verify**

Run: `pytest backend/tests/test_model_schema.py`

- [ ] **Step 3: Update `backend/app/models/model3d.py` and `schemas/model3d.py`**

Ensure `file_size_bytes` is `BigInteger` and add:
```python
is_presupported = Column(Boolean, default=False, nullable=False, index=True)
studio_name = Column(String(100), nullable=True, index=True)
telegram_target_message_id = Column(BigInteger, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_model_schema.py`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/model3d.py backend/app/schemas/model3d.py backend/tests/test_model_schema.py
git commit -m "feat(db): ensure BigInteger file sizes up to 10GB and add studio/presupported columns"
```

---

### Task 2: Fast 3D Parser & Remote Partial Stream Inspector

**Files:**
- Create: `backend/app/services/fast_mesh.py`
- Test: `backend/tests/test_fast_mesh.py`

**Interfaces:**
- Consumes: file path or byte stream
- Produces: `FastMeshInfo(face_count: int, part_count: int, is_presupported: bool, file_list: list[str])`

- [ ] **Step 1: Write unit tests for local and partial stream STL parsing**

```python
# backend/tests/test_fast_mesh.py
import struct
import pytest
from app.services.fast_mesh import parse_stl_header_bytes, inspect_3d_file

def test_parse_stl_header_bytes():
    raw_header = b"\x00" * 80 + struct.pack("<I", 1234567)
    face_count = parse_stl_header_bytes(raw_header)
    assert face_count == 1234567

def test_binary_stl_file(tmp_path):
    stl_file = tmp_path / "huge_10gb_dummy.stl"
    with open(stl_file, "wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", 888888))
    info = inspect_3d_file(str(stl_file))
    assert info.face_count == 888888
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_fast_mesh.py`

- [ ] **Step 3: Implement `backend/app/services/fast_mesh.py`**

Include `parse_stl_header_bytes`, `inspect_3d_file`, and archive keyword scanner (`supported`, `presupported`, `pre_supported`, `chitubox`, `lychee`, `.ctb`, `.pws`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_fast_mesh.py`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fast_mesh.py backend/tests/test_fast_mesh.py
git commit -m "feat(services): implement FastMeshReader with partial stream header parsing"
```

---

### Task 3: AI Tagger Studio & Multi-part Recognition

**Files:**
- Modify: `backend/app/services/ai_tagger.py`
- Test: `backend/tests/test_ai_tagger.py`

**Interfaces:**
- Consumes: filename, message_text, face_count, is_presupported
- Produces: `AITagResult` with `studio: str | None`, `predicted_name: str`, `category: str`, `print_type: str`, `keywords: str`

- [ ] **Step 1: Update AI tagger prompt and response parser to extract studio name**
- [ ] **Step 2: Add heuristic detector for well-known 3D studios (Sanix, Gambody, Wicked, Nomads, etc.)**
- [ ] **Step 3: Run AI tagger tests**
- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ai_tagger.py
git commit -m "feat(ai): add studio recognition and enhanced 3D categorization"
```

---

### Task 4: Worker Pipeline Refactor (Direct Cloud Relay & Zero-Disk Forwarding)

**Files:**
- Modify: `backend/app/worker/processor.py`
- Modify: `backend/app/telegram/downloader.py`
- Test: `backend/tests/test_processor.py`

**Interfaces:**
- Consumes: Arq Redis queue job `process_telegram_message`
- Produces: Processed DB model, Telegram target channel publication with Album + Document + Caption + Inline Buttons, guaranteed temp-file cleanup

- [ ] **Step 1: Implement remote partial MTProto header reader (reading only first 1KB of STL from Telegram)**
- [ ] **Step 2: Implement direct media relay (`send_file(..., file=message.media)`) for zero-disk VPS operation**
- [ ] **Step 3: Format Telegram upload into Media Group Album (photos) + Document (3D file) with styled caption and inline button**
- [ ] **Step 4: Ensure all local temporary directories are purged in `try ... finally`**
- [ ] **Step 5: Commit**

```bash
git add backend/app/worker/processor.py
git commit -m "refactor(worker): implement direct cloud relay, zero-disk forwarding, and telegram album formatter"
```

---

### Task 5: API Endpoints & Streaming Download Support

**Files:**
- Modify: `backend/app/api/models.py`
- Test: `backend/tests/test_api_models.py`

- [ ] **Step 1: Add `is_presupported` and `studio` filter query parameters to `GET /api/v1/models`**
- [ ] **Step 2: Add `GET /api/v1/models/studios` endpoint**
- [ ] **Step 3: Ensure `GET /api/v1/models/{id}/download` uses chunked streaming response for large files**
- [ ] **Step 4: Commit**

```bash
git add backend/app/api/models.py
git commit -m "feat(api): add studio endpoints and chunked stream download"
```

---

### Task 6: Frontend UI/UX Enhancements

**Files:**
- Modify: `frontend/src/components/ModelCard.tsx`
- Modify: `frontend/src/components/SearchFilter.tsx`
- Modify: `frontend/src/components/StlViewer.tsx`
- Modify: `frontend/src/app/dashboard/models/[id]/page.tsx`

- [ ] **Step 1: Update size formatting helper (MB / GB) for files up to 10GB+**
- [ ] **Step 2: In `ModelCard.tsx`, add 🟢 `Pre-Supported` badge, 🏷️ `Studio` tag, and ✈️ Telegram button**
- [ ] **Step 3: In `SearchFilter.tsx`, add Studio dropdown filter & Pre-Supported toggle**
- [ ] **Step 4: In `ModelDetailPage` and `StlViewer.tsx`, switch between 3D Canvas (for `.stl/.obj`) and HD Gallery / Parts Table (for archives)**
- [ ] **Step 5: Add download progress spinner in `ModelDetailPage`**
- [ ] **Step 6: Run frontend build check (`npm run build`)**
- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ModelCard.tsx frontend/src/components/SearchFilter.tsx frontend/src/components/StlViewer.tsx frontend/src/app/dashboard/models/[id]/page.tsx
git commit -m "feat(frontend): format GB file sizes, add pre-supported & studio badges, and smart 3D switcher"
```

---

### Task 7: End-to-End Verification & Documentation

**Files:**
- Modify: `AGENTS.md`
- Test: Full integration test script

- [ ] **Step 1: Run end-to-end processing verification on sample STL and ZIP files**
- [ ] **Step 2: Verify RAM usage remains below 100MB even for large files**
- [ ] **Step 3: Update `AGENTS.md` status table**
- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md with 10GB large file support and lightweight architecture"
```
