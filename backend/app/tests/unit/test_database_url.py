import os

import pytest
from pydantic import ValidationError

os.environ["REDIS_PORT"] = "6379"

from app.core.config import Settings, normalize_database_url


def test_normalize_database_url_uses_asyncpg_for_render_postgres_url():
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )


def test_normalize_database_url_supports_legacy_postgres_scheme():
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )


def test_normalize_database_url_replaces_explicit_sync_drivers():
    assert normalize_database_url("postgresql+psycopg2://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )


def test_normalize_database_url_preserves_asyncpg_and_database_url_prefix():
    url = "DATABASE_URL='postgresql+asyncpg://user:pass@host/db'"
    assert normalize_database_url(url) == "postgresql+asyncpg://user:pass@host/db"


def test_settings_validator_passes_async_url_to_database_clients():
    settings = Settings(
        SECRET_KEY="test-secret",  # noqa: S106 - test-only value
        DATABASE_URL="postgresql://user:pass@host/db",
        REDIS_PORT=6379,
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@host/db"


def test_enabled_whatsapp_requires_exact_https_callback_and_version():
    common = {
        "SECRET_KEY": "test-secret",
        "DATABASE_URL": "postgresql://user:pass@host/db",
        "REDIS_PORT": 6379,
        "WHATSAPP_ENABLED": True,
        "WHATSAPP_APP_ID": "3003",
        "WHATSAPP_APP_SECRET": "synthetic-app-secret",
        "WHATSAPP_WEBHOOK_VERIFY_TOKEN": "synthetic-verify-token",
        "WHATSAPP_API_VERSION": "v23.0",
    }
    settings = Settings(
        **common,
        WHATSAPP_PUBLIC_WEBHOOK_URL="https://api.example.com/api/v1/whatsapp/webhook",
    )
    assert settings.WHATSAPP_API_VERSION == "v23.0"

    with pytest.raises(ValidationError):
        Settings(
            **common,
            WHATSAPP_PUBLIC_WEBHOOK_URL="https://api.example.com/wrong-path?token=unsafe",
        )
