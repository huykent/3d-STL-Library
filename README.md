# 3D STL Library 🧊

An Automated 3D Model Library that crawls Telegram groups for 3D print files (.stl, .obj, .zip, .rar), processes them (geometry analysis, rendering thumbnails, AI tagging via Ollama), and serves a beautiful Next.js web dashboard with a built-in 3D viewer.

## Prerequisites

- **Docker** and **Docker Compose**
- A **Telegram API ID and Hash** (get it from [my.telegram.org](https://my.telegram.org))
- An **Ollama** instance (can be hosted locally or remotely)

## Installation

1. Clone the repository and enter the directory.
2. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and fill in your details:
   - `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_PHONE` are strictly required to login as a userbot.
   - `TELEGRAM_CHAT_IDS` is a comma-separated list of group/channel IDs to monitor.
   - `OLLAMA_BASE_URL` should point to your Ollama API (e.g. `http://host.docker.internal:11434` or a remote URL).
4. Run the stack:
   ```bash
   docker-compose up -d --build
   ```

## Accessing the App

- **Frontend Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs

*Note: On your first login to Telegram, the Telethon userbot may require a 2FA code if your account has a cloud password. The session is saved to a persistent Docker volume after a successful login.*

## Architecture

- **Backend:** Python + FastAPI + SQLAlchemy + Telethon + pyrender + trimesh + arq
- **Frontend:** Next.js 14 + TailwindCSS + Three.js
- **Database:** PostgreSQL for metadata, Redis for queue
- **Storage:** All STL files stay on Telegram's servers. Thumbnails are cached locally.
