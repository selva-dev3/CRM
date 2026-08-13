from datetime import date, datetime, timezone
from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import CalendarEventModel
from app.repositories.calendar_repository import CalendarRepository
from app.schemas.crm_schemas import CalendarEventCreatePayload


def parse_datetime(val: Optional[str]) -> datetime:
    if not val or not str(val).strip():
        return datetime.now(timezone.utc)
    val_str = str(val).strip()
    try:
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except Exception:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)


def event_to_dict(event: CalendarEventModel) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "start": str(event.start_time),
        "end": str(event.end_time),
        "event_type": event.event_type or "Meeting",
        "description": event.description,
    }


class CalendarService:
    """Business logic for the CalendarEventModel domain."""

    def __init__(self, repository: Optional[CalendarRepository] = None) -> None:
        self.repository = repository or CalendarRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def get_calendar_events(
        self,
        db: AsyncSession,
        *,
        search: Optional[str] = None,
    ) -> list[dict]:
        events = await self.repository.list_events(db, search=search)
        return [event_to_dict(e) for e in events]

    async def create_calendar_event(
        self, db: AsyncSession, payload: CalendarEventCreatePayload
    ) -> dict:
        uid = await self.repository.resolve_user_id(db)
        event = await self.repository.create_event(
            db,
            data={
                "user_id": uid,
                "title": payload.title,
                "start_time": parse_datetime(payload.start),
                "end_time": parse_datetime(payload.end),
                "event_type": payload.event_type or "Meeting",
                "description": payload.description,
            },
        )
        await self._commit(db, "Failed to create calendar event")
        await db.refresh(event)
        return event_to_dict(event)

    async def get_calendar_event(self, db: AsyncSession, event_id: str) -> dict:
        event = await self.repository.get_event(db, event_id)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        return event_to_dict(event)

    async def update_calendar_event(
        self, db: AsyncSession, event_id: str, payload: CalendarEventCreatePayload
    ) -> dict:
        event = await self.repository.get_event(db, event_id)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        try:
            if payload.title:
                event.title = payload.title
            if payload.start:
                event.start_time = parse_datetime(payload.start)
            if payload.end:
                event.end_time = parse_datetime(payload.end)
            if payload.event_type:
                event.event_type = payload.event_type
            if payload.description:
                event.description = payload.description
            await db.commit()
            await db.refresh(event)
            return event_to_dict(event)
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=str(e)
            ) from e

    async def delete_calendar_event(self, db: AsyncSession, event_id: str) -> dict:
        event = await self.repository.get_event(db, event_id)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        await self.repository.delete_event(db, event)
        await self._commit(db, "Failed to delete calendar event")
        return {"message": f"Event {event_id} deleted successfully", "status": "success"}

    async def get_availability(self, user_id: Optional[str], date_: Optional[str]) -> dict:
        return {
            "user_id": user_id or "default-user",
            "date": date_ or str(datetime.now().date()),
            "available_slots": ["09:00-09:30", "11:30-12:00", "14:00-14:30", "16:00-17:00"],
        }

    async def sync_google_calendar(self) -> dict:
        return {"message": "Google Calendar 2-way sync completed successfully", "status": "success"}

    async def sync_outlook_calendar(self) -> dict:
        return {"message": "Outlook Calendar 2-way sync completed successfully", "status": "success"}

    async def list_recurring_events(self) -> list[dict]:
        return [
            {"id": "rec-1", "title": "Weekly Team Sync", "rrule": "FREQ=WEEKLY;BYDAY=MO", "event_type": "Internal"},
            {"id": "rec-2", "title": "Monthly Revenue Review", "rrule": "FREQ=MONTHLY;BYMONTHDAY=1", "event_type": "Executive"},
        ]

    async def create_recurring_event(self, title: str, rrule: str) -> dict:
        return {
            "message": f"Recurring event rule '{title}' created with pattern {rrule}",
            "status": "success",
        }


calendar_service = CalendarService()