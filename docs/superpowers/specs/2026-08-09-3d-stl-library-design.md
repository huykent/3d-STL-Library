# 3D STL Library — System Design Spec

**Date:** 2026-08-09  
**Status:** ✅ Design Approved — Ready for Implementation Planning  
**Current Phase:** Brainstorming complete → Next: `writing-plans` skill  

---

## Project Overview

An automated 3D model library system that:
1. Crawls Telegram groups for 3D print files (.stl, .obj, .zip, .rar)
2. Processes files: analyzes geometry, renders thumbnails, AI-tags content
3. Stores metadata in PostgreSQL; files stay on Telegram (no permanent local storage)
4. Serves a web dashboard with gallery view, search/filter, and interactive 3D viewer

---

## Key Architecture Decisions (Locked)

| Decision | Choice | Rationale |
|---|---|---|
| Architecture pattern | Modular Monolith + Async Workers | Balance: simple deploy, modular code |
| Deployment target | Self-hosted VPS (Linux) | User's own server |
| File storage | Telegram Cloud (file_id only) | No local disk cost; re-download on demand |
| Temp file lifecycle | Download → process → delete | Max disk usage: ~1 file at a time |
| Telegram client | Telethon (Userbot) | Access to private/closed groups |
| LLM provider | Ollama on Mac Mini M4 | Free, private, no API cost |
| LLM access | Ollama exposed via Cloudflare Tunnel | VPS calls `https://xxx.trycloudflare.com` |
| Ollama API compat | OpenAI-compatible `/v1/chat/completions` | Drop-in, configurable via `.env` |
| 3D thumbnail | trimesh + pyrender (CPU offscreen) | Headless VPS compatible, no GPU needed |
| Auth | Multi-user with roles (Admin / Viewer) | Admin manages groups/users; Viewer browses/downloads |
| Backend framework | FastAPI (Python, async) | Native asyncio for Telethon + API |
| Frontend framework | Next.js 14 (App Router) + TailwindCSS | |
| 3D web viewer | Three.js (STLLoader) | Browser-side, no server rendering needed |
| Database | PostgreSQL | Metadata, tags, users |
| Queue | Redis + arq (async Redis Queue) | Lightweight, asyncio-native |
| Containerization | Docker + docker-compose | Single-command deploy |

---

## System Architecture

```
┌──────────────────────────── VPS ────────────────────────────────┐
│                                                                   │
│  ┌──────────────────────────────────────────────┐               │
│  │              FastAPI App (api)                │               │
│  │  ┌─────────────────┐  ┌────────────────────┐ │               │
│  │  │ Telegram Listener│  │   REST API         │ │               │
│  │  │ (asyncio task)   │  │   /auth /models    │ │               │
│  │  │ Telethon client  │  │   /tags /admin     │ │               │
│  │  └────────┬─────────┘  └────────────────────┘ │               │
│  └───────────┼────────────────────────────────────┘               │
│              │ push job                                            │
│              ▼                                                     │
│         ┌─────────┐     ┌──────────────────────────────────────┐ │
│         │  Redis  │────►│        Worker Process (arq)          │ │
│         │ (Queue) │     │  1. Download temp STL from Telegram  │ │
│         └─────────┘     │  2. trimesh → analyze + dimensions   │ │
│                         │  3. pyrender → thumbnail PNG         │ │
│                         │  4. Ollama API → AI tags             │ │
│                         │  5. Save to DB, delete temp file     │ │
│                         └──────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────┐   ┌──────────────────────────────────────┐   │
│  │  PostgreSQL    │   │         Next.js Frontend             │   │
│  │  (metadata,    │   │  Gallery / Search / 3D Viewer        │   │
│  │  users, tags)  │   │  (Three.js STL viewer)               │   │
│  └────────────────┘   └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────-─┘
         │                              │
    Telegram API              Mac Mini M4 (Ollama)
    (file storage +           via Cloudflare Tunnel
     re-download)             https://xxx.trycloudflare.com
```

### Processing Flow (new file arrives)
```
Telegram message
  → Telethon handler (event listener, asyncio)
  → Filter: is .stl/.obj/.zip/.rar?
  → If zip/rar: extract, find .stl files inside
  → Push job to Redis queue (one job per .stl file)
  → Worker picks up job:
      1. Download temp file from Telegram
      2. trimesh.load() → face_count, vertex_count, bbox, volume
      3. pyrender offscreen render → thumbnail PNG (saved to thumbnails/)
      4. POST to Ollama API → predicted_name, category, print_type, keywords[]
      5. INSERT to models_3d + tags + model_tags
      6. DELETE temp file
      7. UPDATE processing_status = 'completed'
```

### Download Flow (user clicks Download on dashboard)
```
Browser → GET /api/models/{id}/download
  → FastAPI looks up telegram_file_id in DB
  → Re-download file from Telegram API (stream)
  → StreamingResponse back to browser
  → (no temp file written to disk — streamed directly)
```

---

## Project Structure

```
3d-stl-library/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan startup/shutdown
│   │   ├── config.py               # Pydantic BaseSettings (reads .env)
│   │   ├── database.py             # SQLAlchemy async engine + session factory
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── model3d.py
│   │   │   ├── tag.py
│   │   │   └── source_group.py
│   │   ├── schemas/                # Pydantic v2 request/response schemas
│   │   │   ├── user.py
│   │   │   ├── model3d.py
│   │   │   └── auth.py
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── auth.py             # POST /auth/login, POST /auth/refresh
│   │   │   ├── models.py           # GET /models, GET /models/{id}, GET /models/{id}/download
│   │   │   ├── tags.py             # GET /tags
│   │   │   └── admin.py            # Admin-only: users, source groups management
│   │   ├── services/               # Pure business logic (no FastAPI deps)
│   │   │   ├── stl_analyzer.py     # trimesh: face_count, bbox_mm, volume_mm3, detail_level
│   │   │   ├── thumbnail.py        # pyrender offscreen → PNG file
│   │   │   ├── ai_tagger.py        # HTTP call to Ollama → structured JSON response
│   │   │   └── telegram_storage.py # Re-download file by telegram_file_id
│   │   ├── telegram/               # Telethon userbot
│   │   │   ├── client.py           # TelegramClient init, session management
│   │   │   ├── handlers.py         # on_new_message: filter files, push to Redis
│   │   │   └── downloader.py       # Download + unzip + extract .stl files
│   │   └── worker/
│   │       ├── queue.py            # arq WorkerSettings, Redis connection
│   │       └── processor.py        # process_model_job(): full pipeline function
│   ├── alembic/                    # Alembic DB migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── thumbnails/                 # Stored thumbnail PNGs (permanent, served via API)
│   ├── temp/                       # Temp download dir (auto-cleaned per job)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js 14 App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Redirects to /dashboard
│   │   │   ├── login/page.tsx      # Login form
│   │   │   └── dashboard/
│   │   │       ├── page.tsx        # Gallery grid view
│   │   │       └── models/[id]/page.tsx  # Detail + 3D viewer modal
│   │   ├── components/
│   │   │   ├── ModelCard.tsx       # Thumbnail card in gallery
│   │   │   ├── ModelGrid.tsx       # Responsive grid + infinite scroll
│   │   │   ├── StlViewer.tsx       # Three.js STLLoader (rotate/zoom/pan)
│   │   │   ├── SearchFilter.tsx    # Search + filter chips (detail_level, category)
│   │   │   └── AuthGuard.tsx       # Redirect to /login if no valid JWT
│   │   └── lib/
│   │       ├── api.ts              # Typed API client (axios + interceptors)
│   │       └── auth.ts             # JWT storage, refresh logic
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.yml              # Services: api, worker, postgres, redis, frontend
├── .env.example                    # Template with all required env vars
└── README.md
```

---

## Database Schema

### `users`
```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
username      VARCHAR(50) UNIQUE NOT NULL
email         VARCHAR(255) UNIQUE NOT NULL
password_hash VARCHAR(255) NOT NULL
role          ENUM('admin', 'viewer') DEFAULT 'viewer'
is_active     BOOLEAN DEFAULT true
created_at    TIMESTAMPTZ DEFAULT now()
updated_at    TIMESTAMPTZ DEFAULT now()
```

### `source_groups` — Telegram groups being monitored
```sql
id              SERIAL PRIMARY KEY
chat_id         BIGINT UNIQUE NOT NULL    -- Telegram internal chat ID
name            VARCHAR(255) NOT NULL     -- Display name
username        VARCHAR(255)              -- @handle if public channel
is_active       BOOLEAN DEFAULT true      -- Toggle crawling on/off
model_count     INT DEFAULT 0             -- Cached count
last_message_id BIGINT                    -- Watermark: last processed message ID
created_at      TIMESTAMPTZ DEFAULT now()
```

### `models_3d` — Main model metadata table
```sql
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()

-- File info
original_filename     VARCHAR(500) NOT NULL
file_extension        VARCHAR(10) NOT NULL            -- 'stl', 'obj'
file_size_bytes       BIGINT

-- Telegram storage (replaces local file storage entirely)
telegram_file_id      VARCHAR(500) UNIQUE NOT NULL    -- Used to re-download
telegram_message_id   BIGINT NOT NULL
source_group_id       INT REFERENCES source_groups(id)
telegram_message_text TEXT                            -- Original message content

-- STL Analysis results (NULL until worker completes)
vertex_count          INT
face_count            INT
detail_level          ENUM('low_poly','medium_poly','high_poly','resin_ready')
                      -- Thresholds: <10K | 10K-200K | 200K-1M | >1M faces
bbox_x_mm             FLOAT                           -- Physical bounding box X (mm)
bbox_y_mm             FLOAT
bbox_z_mm             FLOAT
volume_mm3            FLOAT

-- Thumbnail
thumbnail_path        VARCHAR(500)                    -- Relative path to PNG in thumbnails/

-- AI Tagging results (NULL until worker completes)
predicted_name        VARCHAR(500)                    -- AI-predicted model name
ai_category           VARCHAR(100)                    -- Figurine, Mechanical, Functional, etc.
ai_print_type         ENUM('FDM','Resin','Unknown')
ai_keywords           TEXT[]                          -- PostgreSQL native array
ai_raw_response       JSONB                           -- Full LLM response for debugging

-- Processing pipeline status
processing_status     ENUM('pending','processing','completed','failed') DEFAULT 'pending'
processing_error      TEXT                            -- Error message if failed
processing_retries    SMALLINT DEFAULT 0

created_at            TIMESTAMPTZ DEFAULT now()
updated_at            TIMESTAMPTZ DEFAULT now()
```

### `tags` — Normalized tag catalog
```sql
id          SERIAL PRIMARY KEY
name        VARCHAR(100) UNIQUE NOT NULL    -- e.g. "Dragon", "FDM Ready"
slug        VARCHAR(100) UNIQUE NOT NULL    -- e.g. "dragon", "fdm-ready" (URL-safe)
usage_count INT DEFAULT 0                   -- Cached, incremented on model_tags insert
created_at  TIMESTAMPTZ DEFAULT now()
```

### `model_tags` — Many-to-many junction
```sql
model_id    UUID REFERENCES models_3d(id) ON DELETE CASCADE
tag_id      INT REFERENCES tags(id) ON DELETE CASCADE
PRIMARY KEY (model_id, tag_id)
```

### `processing_jobs` — Job audit log & retry tracking
```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
model_id      UUID REFERENCES models_3d(id) ON DELETE CASCADE
job_type      ENUM('full_pipeline','analyze_stl','thumbnail','ai_tag')
status        ENUM('queued','running','done','failed') DEFAULT 'queued'
error_message TEXT
worker_id     VARCHAR(100)       -- Worker hostname (useful for multi-worker debug)
started_at    TIMESTAMPTZ
completed_at  TIMESTAMPTZ
created_at    TIMESTAMPTZ DEFAULT now()
```

### Key Indexes
```sql
CREATE INDEX idx_models_status   ON models_3d(processing_status);
CREATE INDEX idx_models_detail   ON models_3d(detail_level);
CREATE INDEX idx_models_group    ON models_3d(source_group_id);
CREATE INDEX idx_models_created  ON models_3d(created_at DESC);
CREATE INDEX idx_models_fts      ON models_3d
  USING GIN(to_tsvector('english', original_filename || ' ' || COALESCE(telegram_message_text,'')));
CREATE INDEX idx_tags_slug       ON tags(slug);
```

---

## Environment Variables (.env)

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/stl_library

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram (Userbot)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+84xxxxxxxxxx
TELEGRAM_SESSION_NAME=stl_crawler
TELEGRAM_CHAT_IDS=-100xxxxxxxxx,-100yyyyyyyyy   # Comma-separated group IDs

# Ollama (via Cloudflare Tunnel on Mac Mini M4)
OLLAMA_BASE_URL=https://xxx.trycloudflare.com
OLLAMA_MODEL=llama3.2:3b

# JWT Auth
SECRET_KEY=your-super-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Paths
THUMBNAIL_DIR=/app/thumbnails
TEMP_DIR=/app/temp
```

---

## API Endpoints (planned)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | — | Returns JWT access + refresh token |
| POST | `/auth/refresh` | Refresh token | Returns new access token |
| GET | `/models` | Viewer+ | List models (paginated, filterable) |
| GET | `/models/{id}` | Viewer+ | Single model detail |
| GET | `/models/{id}/download` | Viewer+ | Stream file from Telegram |
| GET | `/models/{id}/thumbnail` | Viewer+ | Serve thumbnail PNG |
| GET | `/tags` | Viewer+ | List all tags with usage_count |
| GET | `/admin/groups` | Admin | List source groups |
| POST | `/admin/groups` | Admin | Add Telegram group to monitor |
| PATCH | `/admin/groups/{id}` | Admin | Toggle is_active |
| GET | `/admin/users` | Admin | List users |
| POST | `/admin/users` | Admin | Create user |
| PATCH | `/admin/users/{id}` | Admin | Update role / deactivate |
| GET | `/admin/jobs` | Admin | View processing job queue & history |

---

## Implementation Steps (Execution Plan)

### ✅ Step 1 — Database Schema & Project Structure
**Status: DESIGN APPROVED — not yet coded**
- [ ] Initialize git repo (if not done)
- [ ] Create project directory structure
- [ ] Write SQLAlchemy models
- [ ] Write Alembic migration
- [ ] Write `docker-compose.yml` (postgres + redis only for now)
- [ ] Write `.env.example`

### ⏳ Step 2 — Telegram Listener & Downloader
- [ ] Telethon client setup (session management)
- [ ] Message event handler (filter by file type)
- [ ] Zip/RAR extraction logic
- [ ] Push job to Redis queue (arq)

### ⏳ Step 3 — STL Analyzer + AI Tagger
- [ ] `stl_analyzer.py`: trimesh load → metrics → detail_level enum
- [ ] `thumbnail.py`: pyrender offscreen → PNG
- [ ] `ai_tagger.py`: HTTP POST to Ollama (OpenAI-compat) → parse JSON
- [ ] `processor.py`: full pipeline function, temp file cleanup

### ⏳ Step 4 — FastAPI Backend
- [ ] Auth (JWT, bcrypt, roles)
- [ ] Models endpoints
- [ ] Admin endpoints
- [ ] File streaming for download

### ⏳ Step 5 — Next.js Frontend
- [ ] Auth flow (login, JWT, AuthGuard)
- [ ] Gallery grid with search/filter
- [ ] Three.js STL viewer component
- [ ] Download button

### ⏳ Step 6 — Docker Packaging
- [ ] Backend Dockerfile
- [ ] Frontend Dockerfile
- [ ] Full docker-compose.yml
- [ ] README with setup instructions

---

## Notes & Constraints

- **Thumbnail storage**: The `thumbnails/` directory IS persistent on disk (small PNGs only, no STL files). This is the only permanent local storage.
- **Temp file guarantee**: Worker MUST delete temp file even on failure (try/finally pattern).
- **Ollama prompt engineering**: AI tagger must request strict JSON output. Use Ollama's `format: "json"` parameter to enforce structured output.
- **Telethon session**: Session file (.session) must be persisted via Docker volume so re-auth is not needed on restart.
- **arq vs Celery**: Use `arq` (not Celery) — it is asyncio-native, pairs perfectly with FastAPI's async architecture, and has zero overhead from Celery's worker process model.
- **pyrender headless**: Requires `DISPLAY` env var workaround or `EGL` backend on Linux VPS. Use `os.environ["PYOPENGL_PLATFORM"] = "egl"` before importing pyrender.

---

*Spec written by: AI brainstorming session (2026-08-09)*  
*Next action: Invoke `writing-plans` skill to create detailed implementation plan*
