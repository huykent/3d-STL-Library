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
| Step 1 | ✅ COMPLETE | DB Schema + Project Structure |
| Step 2 | ✅ COMPLETE | Telegram Listener & Downloader |
| Step 3 | ✅ COMPLETE | STL Analyzer + AI Tagger |
| Step 4 | 🟡 NEXT | FastAPI Backend |
| Step 5 | ⏳ Pending | Next.js Frontend |
| Step 6 | ⏳ Pending | Docker Packaging |

**Next action:** Invoke `writing-plans` skill to create implementation plan for Step 4 (FastAPI Backend). Plan file should be at `docs/superpowers/plans/step4-fastapi-backend.md` once written.

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **telebot** (495 symbols, 637 relationships, 10 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/telebot/context` | Codebase overview, check index freshness |
| `gitnexus://repo/telebot/clusters` | All functional areas |
| `gitnexus://repo/telebot/processes` | All execution flows |
| `gitnexus://repo/telebot/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
