from unittest.mock import AsyncMock

import pytest


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
