#!/bin/bash
set -e

# Run database migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start Uvicorn
echo "Starting FastAPI app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
