from __future__ import annotations

import os
import pytest
from unittest.mock import patch


def test_settings_load_from_env():
    """Settings must load required values from environment."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum!!",
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "abcdef1234567890abcdef1234567890",
        "TELEGRAM_PHONE": "+84900000000",
        "TELEGRAM_SESSION_NAME": "test_session",
        "TELEGRAM_CHAT_IDS": "-100111,-100222",
        "OLLAMA_BASE_URL": "https://test.trycloudflare.com",
        "OLLAMA_MODEL": "llama3.2:3b",
        "THUMBNAIL_DIR": "/tmp/thumbnails",
        "TEMP_DIR": "/tmp/temp",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        # Force reload to pick up patched env
        from importlib import reload
        import app.config as config_module
        reload(config_module)
        s = config_module.get_settings()
        assert s.DATABASE_URL == env_vars["DATABASE_URL"]
        assert s.TELEGRAM_API_ID == 12345678
        assert s.chat_ids == [-100111, -100222]
        assert s.OLLAMA_MODEL == "llama3.2:3b"


def test_settings_chat_ids_parsed_as_list():
    """TELEGRAM_CHAT_IDS comma-string must become a list of ints."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum!!",
        "TELEGRAM_API_ID": "99999",
        "TELEGRAM_API_HASH": "abc",
        "TELEGRAM_PHONE": "+1000",
        "TELEGRAM_SESSION_NAME": "s",
        "TELEGRAM_CHAT_IDS": "-100111,-100222,-100333",
        "OLLAMA_BASE_URL": "https://x.cf.com",
        "OLLAMA_MODEL": "llama3.2:3b",
        "THUMBNAIL_DIR": "/tmp/thumbnails",
        "TEMP_DIR": "/tmp/temp",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        from importlib import reload
        import app.config as config_module
        reload(config_module)
        s = config_module.get_settings()
        assert s.chat_ids == [-100111, -100222, -100333]


def test_database_module_exports():
    """database.py must export Base, AsyncSessionLocal, get_db, engine."""
    from app.database import Base, AsyncSessionLocal, get_db, engine
    assert Base is not None
    assert AsyncSessionLocal is not None
    assert engine is not None
    # get_db must be an async generator function
    import inspect
    assert inspect.isasyncgenfunction(get_db)
