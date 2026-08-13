from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Notification
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService, notification_to_dict


def _make_notification(**overrides) -> Notification:
    defaults = {
        "id": "notif-1",
        "user_id": "user-1",
        "title": "Deal Updated",
        "message": "The deal moved to Won",
        "is_read": False,
        "created_at": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Notification(**defaults)


@pytest.mark.asyncio
async def test_list_notifications_filters_unread():
    repo = NotificationRepository()
    repo.list_notifications = AsyncMock(return_value=[_make_notification()])
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_notifications(db, page=1, limit=20, unread_only=True)

    repo.list_notifications.assert_awaited_once()
    assert result[0]["title"] == "Deal Updated"
    assert result[0]["is_read"] is False


@pytest.mark.asyncio
async def test_get_unread_count():
    repo = NotificationRepository()
    repo.list_unread = AsyncMock(return_value=[_make_notification(), _make_notification(id="n2")])
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_unread_count(db)

    assert result["unread_count"] == 2


@pytest.mark.asyncio
async def test_mark_all_notifications_read():
    n1, n2 = _make_notification(), _make_notification(id="n2")
    repo = NotificationRepository()
    repo.list_unread = AsyncMock(return_value=[n1, n2])
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.mark_all_notifications_read(db)

    assert n1.is_read is True
    assert n2.is_read is True
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_system_alert_creates_notification():
    repo = NotificationRepository()
    repo.create_notification = AsyncMock(return_value=_make_notification())
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.send_system_alert(db, "Maintenance", "Down for 10 min")

    created = repo.create_notification.await_args.kwargs["data"]
    assert created["user_id"] == "user-1"
    assert created["title"] == "Maintenance"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_mark_notification_read_not_found():
    repo = NotificationRepository()
    repo.get_notification = AsyncMock(return_value=None)
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.mark_notification_read(db, "missing")


@pytest.mark.asyncio
async def test_delete_notification_commit():
    notification = _make_notification()
    repo = NotificationRepository()
    repo.get_notification = AsyncMock(return_value=notification)
    repo.delete_notification = AsyncMock()
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_notification(db, "notif-1")

    repo.delete_notification.assert_awaited_once_with(db, notification)
    db.commit.assert_awaited_once()
    assert result["message"] == "Notification notif-1 deleted"


@pytest.mark.asyncio
async def test_bulk_delete():
    repo = NotificationRepository()
    repo.list_by_ids = AsyncMock(return_value=[_make_notification()])
    service = NotificationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete(db, ["notif-1"])

    assert result["affected_count"] == 1
    db.commit.assert_awaited_once()


def test_notification_to_dict():
    result = notification_to_dict(_make_notification())
    assert result["id"] == "notif-1"
    assert result["created_at"]