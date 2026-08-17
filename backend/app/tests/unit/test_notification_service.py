from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Notification
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService, notification_to_dict


def _make_notification(**overrides) -> Notification:
    defaults = {
        "id": "notif-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "title": "Deal Updated",
        "message": "The deal moved to Won",
        "is_read": False,
        "created_at": datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Notification(**defaults)


def _service_with(repo, user_repo=None) -> NotificationService:
    return NotificationService(
        repository=repo, user_repository=user_repo or UserRepository()
    )


@pytest.mark.asyncio
async def test_list_notifications_filters_unread():
    repo = NotificationRepository()
    repo.list_notifications = AsyncMock(return_value=[_make_notification()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_notifications(
        db, user_id="user-1", page=1, limit=20, unread_only=True
    )

    repo.list_notifications.assert_awaited_once()
    kwargs = repo.list_notifications.await_args.kwargs
    assert kwargs["user_id"] == "user-1"
    assert kwargs["unread_only"] is True
    assert result[0]["title"] == "Deal Updated"
    assert result[0]["is_read"] is False


@pytest.mark.asyncio
async def test_get_unread_count():
    repo = NotificationRepository()
    repo.count_unread = AsyncMock(return_value=3)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_unread_count(db, user_id="user-1")

    repo.count_unread.assert_awaited_once()
    assert repo.count_unread.await_args.kwargs["user_id"] == "user-1"
    assert result["unread_count"] == 3


@pytest.mark.asyncio
async def test_mark_all_notifications_read():
    n1, n2 = _make_notification(), _make_notification(id="n2")
    repo = NotificationRepository()
    repo.list_unread = AsyncMock(return_value=[n1, n2])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.mark_all_notifications_read(db, user_id="user-1")

    assert n1.is_read is True
    assert n2.is_read is True
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_system_alert_creates_notification():
    repo = NotificationRepository()
    repo.create_notification = AsyncMock(return_value=_make_notification())
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock(return_value=["user-1", "user-2"])
    service = _service_with(repo, user_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.send_system_alert(
        db, user_id="admin-1", org_id="org-1", title="Maintenance", message="Down for 10 min"
    )

    assert repo.create_notification.await_count == 2
    first_created = repo.create_notification.await_args_list[0].kwargs["data"]
    assert first_created["user_id"] == "user-1"
    assert first_created["title"] == "Maintenance"
    assert first_created["event_name"] == "system.alert"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_mark_notification_read_not_found():
    repo = NotificationRepository()
    repo.get_notification = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.mark_notification_read(
            db, user_id="user-1", notification_id="missing"
        )


@pytest.mark.asyncio
async def test_delete_notification_commit():
    notification = _make_notification()
    repo = NotificationRepository()
    repo.get_notification = AsyncMock(return_value=notification)
    repo.delete_notification = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_notification(
        db, user_id="user-1", notification_id="notif-1"
    )

    repo.get_notification.assert_awaited_once()
    assert repo.get_notification.await_args.kwargs["user_id"] == "user-1"
    repo.delete_notification.assert_awaited_once_with(db, notification)
    db.commit.assert_awaited_once()
    assert result["message"] == "Notification notif-1 deleted"


@pytest.mark.asyncio
async def test_bulk_delete():
    repo = NotificationRepository()
    repo.list_by_ids = AsyncMock(return_value=[_make_notification()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete(db, user_id="user-1", ids=["notif-1"])

    repo.list_by_ids.assert_awaited_once()
    assert repo.list_by_ids.await_args.kwargs["user_id"] == "user-1"
    assert result["affected_count"] == 1
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# notify() dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_assignee_or_org_uses_assignee():
    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=False)
    repo.create_notification = AsyncMock()
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock()
    service = _service_with(repo, user_repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify(
        db,
        event_name="lead.created",
        organization_id="org-1",
        actor_user_id="user-9",
        entity_type="lead",
        entity_id="lead-1",
        assigned_to="user-2",
        data={"id": "lead-1", "title": "Acme"},
    )

    user_repo.list_active_ids_by_org.assert_not_awaited()
    created = repo.create_notification.await_args.kwargs["data"]
    assert created["user_id"] == "user-2"
    assert created["organization_id"] == "org-1"
    assert created["event_name"] == "lead.created"
    assert created["entity_type"] == "lead"
    assert created["entity_id"] == "lead-1"
    repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_assignee_or_org_falls_back_to_org_wide():
    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=False)
    repo.create_notification = AsyncMock()
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock(return_value=["user-1", "user-2", "user-3"])
    service = _service_with(repo, user_repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify(
        db,
        event_name="deal.created",
        organization_id="org-1",
        actor_user_id="user-1",
        entity_type="deal",
        entity_id="deal-1",
        assigned_to=None,
        data={"id": "deal-1"},
    )

    user_repo.list_active_ids_by_org.assert_awaited_once()
    assert user_repo.list_active_ids_by_org.await_args.args[1] == "org-1"
    created_ids = [c.kwargs["data"]["user_id"] for c in repo.create_notification.await_args_list]
    assert created_ids == ["user-2", "user-3"]
    repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_skips_dedup_when_unread_exists():
    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=True)
    repo.create_notification = AsyncMock()
    service = _service_with(repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify(
        db,
        event_name="lead.created",
        organization_id="org-1",
        entity_type="lead",
        entity_id="lead-1",
        assigned_to="user-2",
        data={},
    )

    repo.create_notification.assert_not_awaited()
    repo.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_assignee_only_event():
    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=False)
    repo.create_notification = AsyncMock()
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock()
    service = _service_with(repo, user_repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify(
        db,
        event_name="task.completed",
        organization_id="org-1",
        entity_type="task",
        entity_id="task-1",
        assigned_to="user-7",
        data={"id": "task-1"},
    )

    user_repo.list_active_ids_by_org.assert_not_awaited()
    created = repo.create_notification.await_args.kwargs["data"]
    assert created["user_id"] == "user-7"


@pytest.mark.asyncio
async def test_notify_org_wide_event():
    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=False)
    repo.create_notification = AsyncMock()
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock(return_value=["user-1", "user-2"])
    service = _service_with(repo, user_repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify(
        db,
        event_name="invoice.paid",
        organization_id="org-1",
        entity_type="invoice",
        entity_id="inv-1",
        data={"id": "inv-1", "invoice_number": "INV-001"},
    )

    user_repo.list_active_ids_by_org.assert_awaited_once()
    assert repo.create_notification.await_count == 2


@pytest.mark.asyncio
async def test_notify_in_app_does_not_dispatch_slack(monkeypatch):
    from app.services.integration_service import integration_service

    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(return_value=False)
    repo.create_notification = AsyncMock()
    user_repo = UserRepository()
    user_repo.list_active_ids_by_org = AsyncMock(return_value=["user-2"])
    service = _service_with(repo, user_repo)
    service.repository.commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)
    slack_notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", slack_notify)

    await service.notify_in_app(
        db,
        event_name="integration.connected",
        organization_id="org-1",
        entity_type="integration",
        entity_id="int-1",
        data={"provider": "slack"},
    )

    slack_notify.assert_not_awaited()
    created = repo.create_notification.await_args.kwargs["data"]
    assert created["event_name"] == "integration.connected"


@pytest.mark.asyncio
async def test_notify_in_app_failure_still_dispatches_slack(monkeypatch):
    from app.services.integration_service import integration_service

    repo = NotificationRepository()
    repo.exists_unread = AsyncMock(side_effect=RuntimeError("db down"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    slack_notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", slack_notify)

    await service.notify(
        db,
        event_name="lead.created",
        organization_id="org-1",
        entity_type="lead",
        entity_id="lead-1",
        assigned_to="user-2",
        data={},
    )

    slack_notify.assert_awaited_once()
    kwargs = slack_notify.await_args.kwargs
    assert kwargs["event_name"] == "lead.created"
    assert kwargs["org_id"] == "org-1"


def test_notification_to_dict():
    result = notification_to_dict(_make_notification())
    assert result["id"] == "notif-1"
    assert result["created_at"]
    assert result["organization_id"] == "org-1"
    assert result["event_name"] is None
    assert result["payload"] is None
    assert result["read_at"] is None
