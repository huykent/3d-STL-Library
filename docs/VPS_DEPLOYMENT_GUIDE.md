# Deployment Guide: Fresh Ubuntu VPS

This guide will walk you through setting up the 3D STL Library project on a brand new Ubuntu VPS.

## Prerequisites
- A fresh Ubuntu server (e.g., Ubuntu 22.04 LTS or 24.04 LTS).
- A domain name (optional, but recommended if you plan to set up HTTPS later).
- Root or `sudo` access to the server.

---

## Step 1: System Setup and Updates

Log into your new VPS as `root` (or a user with sudo privileges) and update the system packages:

```bash
sudo apt update && sudo apt upgrade -y
```

Install essential utilities:
```bash
sudo apt install -y git curl wget nano unzip
```

---

## Step 2: Install Docker & Docker Compose

We need Docker to run the containerized backend, frontend, database, and Redis.

Install Docker:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

Ensure Docker Compose plugin is installed (modern Docker includes this by default):
```bash
sudo apt-get install -y docker-compose-plugin
```

Verify the installation:
```bash
docker --version
docker compose version
```

---

## Step 3: Clone the Repository

Clone your codebase to the server (you may need to set up SSH keys or use a personal access token if your repo is private):

```bash
# Clone the repository (replace with your actual git URL)
git clone https://github.com/your-username/3d-STL-Library.git
cd 3d-STL-Library
```

*Note: Alternatively, you can use the `scripts/deploy.py` script from your local machine to push the code directly to the server without needing to clone via Git.*

---

## Step 4: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Open the `.env` file to edit the secrets:
   ```bash
   nano .env
   ```

3. **Required values to fill in:**
   - `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` / `TELEGRAM_PHONE`: Your telegram credentials.
   - `SECRET_KEY`: Generate a random secure string for JWT (e.g., run `openssl rand -hex 32`).
   - `OLLAMA_BASE_URL`: Make sure this points to your Mac Mini M4 Cloudflare Tunnel URL.
   - Update database passwords if necessary (ensure they match the docker-compose setup).

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## Step 5: Start the Services

Once your environment is configured, use Docker Compose to build and start the entire stack in detached mode:

```bash
docker compose up -d --build
```

Docker will now download PostgreSQL and Redis images, and build the custom containers for the FastAPI backend and Next.js frontend.

---

## Step 6: Verify the Deployment

Check if all containers are running:
```bash
docker compose ps
```

Check the logs to ensure the FastAPI app and Worker are running without errors:
```bash
# View all logs
docker compose logs -f

# View backend logs specifically
docker compose logs -f api

# View worker logs specifically
docker compose logs -f worker
```

**Testing the Web Interface:**
Navigate to `http://YOUR_SERVER_IP:3000` in your web browser to access the frontend dashboard! (Make sure port 3000 and 8000 are open on your VPS firewall if you are accessing them directly without a reverse proxy).

---

## (Optional) Step 7: Set up Nginx as a Reverse Proxy

For production, you should place Nginx in front of your Docker containers to handle port 80/443 and SSL certificates (via Let's Encrypt).

1. Install Nginx:
   ```bash
   sudo apt install -y nginx
   ```
2. Set up Certbot for SSL:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   ```
3. Configure an Nginx site pointing your domain to `localhost:3000` (frontend) and `/api/` to `localhost:8000` (backend).
