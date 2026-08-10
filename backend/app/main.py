from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info(f"Starting STL Library API | env={settings.APP_ENV}")
    
    from app.telegram.client import start_telegram_client, stop_telegram_client
    from app.telegram.handlers import register_handlers
    
    # Do not start telethon in tests unless explicitly enabled
    if settings.APP_ENV != "test" and settings.TELEGRAM_API_ID:
        try:
            register_handlers()
            await start_telegram_client()
            logger.info("Telegram client started and handlers registered")
        except Exception as e:
            logger.error(f"Failed to start telegram client: {e}")
            
    yield
    
    logger.info("Shutting down STL Library API")
    if settings.APP_ENV != "test" and settings.TELEGRAM_API_ID:
        try:
            await stop_telegram_client()
        except Exception as e:
            logger.error(f"Error stopping telegram client: {e}")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="3D STL Library API",
        description="Automated 3D model library — crawls Telegram, processes STL files",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Step 5 will restrict to frontend origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "ok", "env": settings.APP_ENV}

    # Routers will be added in Step 4:
    # app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    # app.include_router(models_router, prefix="/models", tags=["Models"])
    # app.include_router(tags_router, prefix="/tags", tags=["Tags"])
    # app.include_router(admin_router, prefix="/admin", tags=["Admin"])

    return app


app = create_app()
