from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Meeting
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.crm_schemas import MeetingCreate
from app.services.integration_service import integration_service
from app.services.meeting_service import MeetingService, parse_datetime


def _make_meeting(**overrides) -> Meeting:
    defaults = {
        "id": "mtg-1",
        "organization_id": "org-1",
        "title": "Product Demo",
        "start_time": datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 8, 1, 11, 0, tzinfo=timezone.utc),
        "meeting_link": "https://meet.google.com/x",
        "ai_summary": None,
    }
    defaults.update(overrides)
    return Meeting(**defaults)


def _service_with(repo: MeetingRepository) -> MeetingService:
    return MeetingService(repository=repo)


def test_parse_datetime_handles_iso_date_and_empty():
    assert parse_datetime("2026-08-01") == datetime(2026, 8, 1)
    assert parse_datetime("2026-08-01T10:30:00") == datetime(2026, 8, 1, 10, 30)
    assert parse_datetime("2026-08-01T10:30:00Z").tzinfo is not None
    assert parse_datetime("not-a-date") is not None
    assert parse_datetime("") is not None


@pytest.mark.asyncio
async def test_get_meeting_raises_not_found_when_missing():
    repo = MeetingRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_meeting(db, "missing-meeting")


@pytest.mark.asyncio
async def test_schedule_meeting_resolves_org_and_saves_attendees(monkeypatch):
    meeting = _make_meeting()
    repo = MeetingRepository()
    repo.create = AsyncMock(return_value=meeting)
    repo.create_attendee = AsyncMock()
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.meeting_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = MeetingCreate(
        title="Product Demo",
        start_time="2026-08-01T10:00:00",
        end_time="2026-08-01T11:00:00",
        attendee_emails=["a@crm.com", "b@crm.com"],
    )
    result = await service.schedule_meeting(db, payload)

    assert result["id"] == "mtg-1"
    assert result["title"] == "Product Demo"
    repo.create.assert_awaited_once()
    assert repo.create_attendee.await_count == 2


@pytest.mark.asyncio
async def test_schedule_meeting_fires_meeting_created_event(monkeypatch):
    meeting = _make_meeting()
    repo = MeetingRepository()
    repo.create = AsyncMock(return_value=meeting)
    repo.create_attendee = AsyncMock()
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.services.meeting_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.schedule_meeting(
        db,
        MeetingCreate(
            title="Product Demo",
            start_time="2026-08-01T10:00:00",
            end_time="2026-08-01T11:00:00",
            attendee_emails=["a@crm.com"],
        ),
    )

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "meeting.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["attendees"] == ["a@crm.com"]


@pytest.mark.asyncio
async def test_schedule_meeting_without_attendees_skips_attendee_creation(monkeypatch):
    meeting = _make_meeting()
    repo = MeetingRepository()
    repo.create = AsyncMock(return_value=meeting)
    repo.create_attendee = AsyncMock()
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.meeting_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = MeetingCreate(
        title="Product Demo",
        start_time="2026-08-01T10:00:00",
        end_time="2026-08-01T11:00:00",
        attendee_emails=[],
    )
    result = await service.schedule_meeting(db, payload)

    assert result["id"] == "mtg-1"
    repo.create_attendee.assert_not_awaited()


@pytest.mark.asyncio
async def test_rsvp_creates_missing_attendee():
    meeting = _make_meeting()
    repo = MeetingRepository()
    repo.get_by_id = AsyncMock(return_value=meeting)
    repo.get_attendee = AsyncMock(return_value=None)
    repo.create_attendee = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.rsvp(db, "mtg-1", "a@crm.com", "accepted")

    assert result["message"] == "RSVP 'accepted' recorded for a@crm.com"
    repo.create_attendee.assert_awaited_once()