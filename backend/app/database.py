from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base — all ORM models inherit from this."""
    pass


def _create_engine():
    # Import here to avoid triggering settings load at module-level
    from app.config import get_settings
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def _create_session_factory(eng):
    return async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# Lazy singletons — only created on first access
_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = _create_session_factory(_get_engine())
    return _session_factory


class _LazyEngine:
    """Proxy object that behaves like an engine but only creates it on use."""
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

    def __repr__(self):
        return repr(_get_engine())


class _LazySessionFactory:
    """Proxy that behaves like async_sessionmaker but only creates it on use."""
    def __call__(self, *args, **kwargs):
        return _get_session_factory()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_get_session_factory(), name)


# Public exports — engine and AsyncSessionLocal are lazy proxies
engine = _LazyEngine()
AsyncSessionLocal = _LazySessionFactory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session, rolls back on error."""
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
