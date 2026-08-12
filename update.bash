#!/bin/bash

# Navigate to the script's directory (assuming it's in the project root)
cd "$(dirname "$0")"

echo "=========================================="
echo "    Updating 3D STL Library Server        "
echo "=========================================="

echo "1. Pulling latest code from GitHub..."
git pull origin main

echo "2. Rebuilding Docker images (without cache) and restarting containers..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "=========================================="
echo "    Update completed successfully!        "
echo "=========================================="
