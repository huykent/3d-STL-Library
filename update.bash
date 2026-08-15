#!/bin/bash

# Navigate to the script's directory (assuming it's in the project root)
cd "$(dirname "$0")"

echo "=========================================="
echo "    Updating 3D STL Library Server        "
echo "=========================================="

echo "1. Pulling latest code from GitHub..."
OUTPUT=$(git pull origin main)
echo "$OUTPUT"

if echo "$OUTPUT" | grep -q "Already up to date."; then
    echo "No new changes found. Skipping Docker restart."
else
    echo "2. Cleaning up Docker build cache & dangling images to free disk space..."
    docker builder prune -f
    docker image prune -f

    echo "3. Rebuilding Docker images and restarting containers..."
    docker compose down
    docker compose build --no-cache
    docker compose up -d
fi

echo "=========================================="
echo "    Update completed successfully!        "
echo "=========================================="

