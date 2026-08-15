from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_redis_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    setup_redis_logging("API")
    settings = get_settings()
    logger.info(f"Starting STL Library API | env={settings.APP_ENV}")
    
    # Auto-seed default admin user if database is empty
    if settings.APP_ENV != "test":
        try:
            from app.database import AsyncSessionLocal
            from app.models.user import User, UserRole
            from app.services.auth_service import get_password_hash
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                res = await session.execute(select(User).where(User.username == "admin"))
                if not res.scalar_one_or_none():
                    admin_user = User(
                        username="admin",
                        email="admin@example.com",
                        password_hash=get_password_hash("admin"),
                        role=UserRole.admin,
                        is_active=True
                    )
                    session.add(admin_user)
                    await session.commit()
                    logger.info("Successfully seeded default admin user: admin / admin")
        except Exception as seed_err:
            logger.warning(f"Could not seed default admin user on startup: {seed_err}")

    from app.telegram.client import start_telegram_client, stop_telegram_client
    from app.telegram.handlers import register_handlers
    
    # Do not start telethon in tests unless explicitly enabled
    if settings.APP_ENV != "test" and settings.TELEGRAM_API_ID:
        try:
            await register_handlers()
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

    # Auth
    from app.api.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    
    # Users (AdminCP/UserCP)
    from app.api.users import router as users_router
    app.include_router(users_router, prefix="/api/users", tags=["Users"])

    # Models
    from app.api.models import router as models_router
    app.include_router(models_router, prefix="/api/models", tags=["Models"])

    # Tags
    from app.api.tags import router as tags_router
    app.include_router(tags_router, prefix="/api/tags", tags=["Tags"])

    # Admin
    from app.api.admin import router as admin_router
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
    
    # Upload
    from app.api.upload import router as upload_router
    app.include_router(upload_router, prefix="/api/admin", tags=["Upload"])

    # Logs
    from app.api.logs import router as logs_router
    app.include_router(logs_router, prefix="/api/admin/logs", tags=["Logs"])

    return app


app = create_app()
