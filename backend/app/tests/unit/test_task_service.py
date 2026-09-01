from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.crm_schemas import TaskCreate, TaskUpdate
from app.services.integration_service import integration_service
from app.services.task_service import TaskService, parse_datetime


def _make_task(**overrides) -> Task:
    defaults = {
        "id": "task-1",
        "organization_id": "org-1",
        "title": "Follow up",
        "description": None,
        "priority": "Medium",
        "status": "Pending",
        "due_date": datetime(2026, 8, 1),
        "assigned_to": "usr-1",
    }
    defaults.update(overrides)
    return Task(**defaults)


def _service_with(repo: TaskRepository) -> TaskService:
    return TaskService(repository=repo)


def test_parse_datetime_handles_iso_date_and_invalid_input():
    assert parse_datetime("2026-08-01") == datetime(2026, 8, 1)
    assert parse_datetime("2026-08-01T10:30:00") == datetime(2026, 8, 1, 10, 30)
    parsed_utc = parse_datetime("2026-08-01T10:30:00Z")
    assert parsed_utc is not None
    assert parsed_utc.tzinfo is not None
    assert parse_datetime("") is None
    assert parse_datetime("not-a-date") is None


@pytest.mark.asyncio
async def test_get_task_raises_not_found_when_missing():
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_task(db, "missing-task")


@pytest.mark.asyncio
async def test_create_task_resolves_org_and_serializes(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.create = AsyncMock(return_value=task)
    repo.get_user_by_id_name_email = AsyncMock(return_value=None)
    repo.get_first_user = AsyncMock(return_value=User(id="usr-2"))
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.task_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = TaskCreate(title="Follow up")
    result = await service.create_task(db, payload)

    assert result["id"] == "task-1"
    assert result["status"] == "Pending"
    assert result["priority"] == "Medium"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_task_fires_task_created_event(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.create = AsyncMock(return_value=task)
    repo.get_user_by_id_name_email = AsyncMock(return_value=None)
    repo.get_first_user = AsyncMock(return_value=User(id="usr-2"))
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.services.task_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.create_task(db, TaskCreate(title="Follow up"))

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "task.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["title"] == "Follow up"


@pytest.mark.asyncio
async def test_complete_task_fires_task_completed_event(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.complete_task(db, "task-1")

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "task.completed"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["status"] == "Completed"


@pytest.mark.asyncio
async def test_update_task_applies_only_provided_fields():
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_task(db, "task-1", TaskUpdate(status="Completed"))

    assert task.status == "Completed"
    assert task.priority == "Medium"
    assert task.title == "Follow up"
    assert result["status"] == "Completed"


@pytest.mark.asyncio
async def test_bulk_complete_updates_all_matching_tasks():
    t1 = _make_task(id="t1")
    t2 = _make_task(id="t2")
    repo: Any = TaskRepository()
    repo.list_by_ids = AsyncMock(return_value=[t1, t2])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_complete(db, ["t1", "t2"])

    assert result["affected_count"] == 2
    assert t1.status == "Completed"
    assert t2.status == "Completed"


@pytest.mark.asyncio
async def test_assign_task_resolves_user_id(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    repo.get_user_by_id_name_email = AsyncMock(return_value=User(id="usr-9"))
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    result = await service.assign_task(db, "task-1", "usr-9")

    assert task.assigned_to == "usr-9"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_assign_task_fires_task_assigned_event(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    repo.get_user_by_id_name_email = AsyncMock(return_value=User(id="usr-9"))
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.assign_task(db, "task-1", "usr-9")

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "task.assigned"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["assigned_to"] == "usr-9"


@pytest.mark.asyncio
async def test_update_task_fires_priority_changed_event(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_task(db, "task-1", TaskUpdate(priority="High"))

    assert task.priority == "High"
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "task.priority_changed"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["old_priority"] == "Medium"


@pytest.mark.asyncio
async def test_update_task_no_priority_event_when_unchanged(monkeypatch):
    task = _make_task()
    repo: Any = TaskRepository()
    repo.get_by_id = AsyncMock(return_value=task)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_task(db, "task-1", TaskUpdate(status="Completed"))

    notify.assert_not_awaited()
