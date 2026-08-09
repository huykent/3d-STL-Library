# AGENTS.md — 3D STL Library Project

> **AI Agent Orientation File.** Read this first before any action in this repository.

---

## What Is This Project?

An **Automated 3D Model Library** — a full-stack system that:
1. **Crawls** Telegram groups (via Telethon userbot) for 3D print files (.stl, .obj, .zip, .rar)
2. **Processes** each file: geometry analysis (trimesh), thumbnail rendering (pyrender), AI tagging (Ollama)
3. **Stores** only metadata in PostgreSQL — files stay on Telegram's servers (re-downloaded on demand)
4. **Serves** a Next.js web dashboard with gallery, search/filter, and interactive Three.js 3D viewer

---

## Current Status

**Phase: Design Complete → Implementation Not Started**

| Step | Status | Description |
|---|---|---|
| Step 1 | 🟡 DESIGN APPROVED | DB Schema + Project Structure |
| Step 2 | ⏳ Pending | Telegram Listener & Downloader |
| Step 3 | ⏳ Pending | STL Analyzer + AI Tagger |
| Step 4 | ⏳ Pending | FastAPI Backend |
| Step 5 | ⏳ Pending | Next.js Frontend |
| Step 6 | ⏳ Pending | Docker Packaging |

**Next action:** Read the design spec, then invoke `writing-plans` skill to create a detailed implementation plan for Step 1.

---

## Full Design Spec

📄 **[docs/superpowers/specs/2026-08-09-3d-stl-library-design.md](docs/superpowers/specs/2026-08-09-3d-stl-library-design.md)**

This file contains everything: architecture decisions, DB schema, folder structure, API endpoints, environment variables, and implementation notes. **Read it before writing any code.**

---

## Tech Stack (Locked — Do Not Change Without User Approval)

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + FastAPI (async) |
| Telegram | Telethon (Userbot — personal account) |
| Queue | arq (asyncio-native Redis queue) |
| 3D Analysis | trimesh |
| Thumbnail | pyrender (CPU offscreen, EGL backend) |
| AI Tagging | Ollama on Mac Mini M4 via Cloudflare Tunnel |
| Database | PostgreSQL (SQLAlchemy async + Alembic) |
| Frontend | Next.js 14 (App Router) + TailwindCSS |
| 3D Viewer | Three.js STLLoader |
| Deployment | Docker + docker-compose |

---

## Critical Architecture Constraints

1. **No permanent local file storage** — STL files are NOT stored on the VPS. Only thumbnails (small PNGs) are kept. All STL files are re-downloaded from Telegram on demand using `telegram_file_id`.

2. **Temp files MUST be cleaned up** — Worker must delete temp files in a `try/finally` block even on failure.

3. **Telethon = Userbot** — Uses the owner's personal Telegram account credentials (API_ID, API_HASH, phone). NOT a bot token. Session file must be persisted via Docker volume.

4. **Ollama endpoint** — Mac Mini M4 runs Ollama, exposed via Cloudflare Tunnel as an OpenAI-compatible API. Configure `OLLAMA_BASE_URL` in `.env`.

5. **pyrender on headless Linux** — Must set `os.environ["PYOPENGL_PLATFORM"] = "egl"` before importing pyrender in Docker/VPS environment.

6. **Use `arq` not Celery** — arq is asyncio-native, works perfectly with FastAPI's async architecture.

---

## Tools Available

- **GitNexus** (`npx gitnexus analyze`) — Indexes codebase into knowledge graph. Use after writing significant code. Query with `gitnexus query`, `gitnexus context`, `gitnexus impact`.
- **Superpowers Skills** — Available in `superpowers/skills/` and `node_modules/gitnexus/skills/`

---

## How to Continue Work

1. Read `docs/superpowers/specs/2026-08-09-3d-stl-library-design.md`
2. Check the Implementation Steps table above to find current status
3. Invoke the appropriate skill (`writing-plans`, `subagent-driven-development`, etc.)
4. Follow the 6-step implementation order

---

## Environment Variables Needed

Copy `.env.example` to `.env` and fill in:
- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` / `TELEGRAM_PHONE` — from https://my.telegram.org
- `TELEGRAM_CHAT_IDS` — comma-separated Telegram group IDs to monitor
- `OLLAMA_BASE_URL` — Cloudflare Tunnel URL for Mac Mini M4 Ollama instance
- `SECRET_KEY` — JWT secret (generate with `openssl rand -hex 32`)
- `DATABASE_URL` / `REDIS_URL` — auto-configured in docker-compose

See full `.env.example` once Step 1 is implemented.
