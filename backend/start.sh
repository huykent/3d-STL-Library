#!/bin/bash

# Run database migrations
echo "Running Alembic migrations..."
alembic upgrade head || echo "Warning: Alembic migrations encountered an issue, proceeding to start API..."

# Start Uvicorn
echo "Starting FastAPI app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

