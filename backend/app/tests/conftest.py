import os
from unittest.mock import AsyncMock

import pytest

# Keep collection and unit tests runnable from a fresh checkout without
# requiring developer credentials. CI and local service variables override
# these defaults through the environment.
os.environ.setdefault("CRM_DISABLE_DOTENV", "1")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_test"
)
os.environ.setdefault(
    "CRM_WORKFLOW_TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_test",
)
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "minioadmin")
os.environ.setdefault("AWS_S3_BUCKET", "crm-test-bucket")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")


@pytest.fixture(autouse=True)
def isolate_notification_dispatch(monkeypatch):
    """Keep service unit tests from executing the real notification repository.

    Entity-service tests use AsyncMock sessions rather than a database. Letting
    the process-wide notification dispatcher reach its real user repository
    creates unawaited database coroutines. Keep dispatch itself real so tests
    can still verify downstream integration notifications.
    """
    from app.services.notification_service import notification_service

    monkeypatch.setattr(
        notification_service.user_repository,
        "list_active_ids_by_org",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        notification_service.repository,
        "exists_unread",
        AsyncMock(return_value=True),
    )


def pytest_sessionfinish(session, exitstatus):
    """Make missing integration services fail CI instead of being skipped."""
    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = terminal_reporter.stats.get("skipped", []) if terminal_reporter else []
    if skipped:
        session.exitstatus = 1
