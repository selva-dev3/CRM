from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import CalendarEventModel, User
from app.repositories.calendar_repository import CalendarRepository
from app.schemas.crm_schemas import CalendarEventCreatePayload
from app.services.calendar_service import CalendarService, event_to_dict, parse_datetime


def _make_event(**overrides) -> CalendarEventModel:
    defaults = {
        "id": "evt-1",
        "user_id": "user-1",
        "title": "Demo Meeting",
        "description": None,
        "start_time": datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
        "end_time": datetime(2026, 8, 10, 11, 0, tzinfo=UTC),
        "event_type": "Meeting",
    }
    defaults.update(overrides)
    return CalendarEventModel(**defaults)


def _user() -> User:
    return User(id="user-1", email="user@crm.com", organization_id="org-1")


@pytest.fixture(autouse=True)
def _stub_organization_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.services.calendar_service.organization_service.resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )


@pytest.mark.asyncio
async def test_get_calendar_events_maps_rows():
    repo: Any = CalendarRepository()
    repo.list_events = AsyncMock(return_value=[_make_event()])
    service = CalendarService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_calendar_events(db, search="demo", current_user=_user())

    assert result[0]["title"] == "Demo Meeting"
    assert result[0]["event_type"] == "Meeting"
    repo.list_events.assert_awaited_once_with(
        db, organization_id="org-1", search="demo"
    )


@pytest.mark.asyncio
async def test_create_calendar_event_resolves_user(monkeypatch):
    event = _make_event()
    repo: Any = CalendarRepository()
    repo.create_event = AsyncMock(return_value=event)
    service = CalendarService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_calendar_event(
        db,
        CalendarEventCreatePayload(
            title="Demo", start="2026-08-10T10:00:00Z", end="2026-08-10T11:00:00Z"
        ),
        current_user=_user(),
    )

    created = repo.create_event.await_args_list[-1].kwargs["data"]
    assert created["user_id"] == "user-1"
    assert created["title"] == "Demo"
    assert result["id"] == "evt-1"
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_calendar_event_not_found():
    repo: Any = CalendarRepository()
    repo.get_event = AsyncMock(return_value=None)
    service = CalendarService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_calendar_event(db, "missing", _user())
    repo.get_event.assert_awaited_once_with(db, "missing", "org-1")


@pytest.mark.asyncio
async def test_update_calendar_event_partial():
    event = _make_event()
    repo: Any = CalendarRepository()
    repo.get_event = AsyncMock(return_value=event)
    service = CalendarService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_calendar_event(
        db,
        "evt-1",
        CalendarEventCreatePayload(title="Renamed", start="", end=""),
        _user(),
    )

    assert event.title == "Renamed"
    assert result["title"] == "Renamed"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_calendar_event_commit():
    event = _make_event()
    repo: Any = CalendarRepository()
    repo.get_event = AsyncMock(return_value=event)
    repo.delete_event = AsyncMock()
    service = CalendarService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_calendar_event(db, "evt-1", _user())

    repo.delete_event.assert_awaited_once_with(db, event)
    assert result["status"] == "success"


def test_parse_datetime_handles_z_suffix():
    parsed = parse_datetime("2026-08-10T10:00:00Z")
    assert parsed.tzinfo is not None
    assert parsed.hour == 10


def test_parse_datetime_falls_back_to_now():
    parsed = parse_datetime("not-a-date")
    assert isinstance(parsed, datetime)


def test_event_to_dict_defaults_event_type():
    result = event_to_dict(_make_event(event_type=None))
    assert result["event_type"] == "Meeting"
