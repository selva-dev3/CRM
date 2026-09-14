from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import CalendarEventModel, User
from app.repositories.calendar_repository import CalendarRepository
from app.schemas.crm_schemas import CalendarEventCreatePayload
from app.services.org_service import organization_service
from app.services.record_access_service import record_access_service


def parse_datetime(val: str | None) -> datetime:
    if not val or not str(val).strip():
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="CALENDAR_DATETIME_REQUIRED",
            message="Calendar event date and time are required",
        )
    val_str = str(val).strip()
    try:
        parsed = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except ValueError as exc:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_CALENDAR_DATETIME",
                message="Calendar event date and time must be valid ISO-8601 values",
            ) from exc


def event_to_dict(event: CalendarEventModel) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "start": str(event.start_time),
        "end": str(event.end_time),
        "event_type": event.event_type or "Meeting",
        "description": event.description,
        "status": event.status,
    }


class CalendarService:
    """Business logic for the CalendarEventModel domain."""

    def __init__(self, repository: CalendarRepository | None = None) -> None:
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
        search: str | None = None,
        page: int = 1,
        limit: int = 50,
        start_date: str | None = None,
        end_date: str | None = None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access = await record_access_service.resolve(db, current_user, "calendar")
        start = parse_datetime(start_date) if start_date else None
        end = parse_datetime(end_date) if end_date else None
        if start and end and end < start:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_CALENDAR_RANGE",
                message="Calendar end date must not be before start date",
            )
        events = await self.repository.list_events(
            db,
            organization_id=org_id,
            search=search,
            page=page,
            limit=limit,
            start=start,
            end=end,
            access=access,
        )
        return [event_to_dict(e) for e in events]

    async def count_calendar_events(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        current_user: User,
    ) -> int:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access = await record_access_service.resolve(db, current_user, "calendar")
        start = parse_datetime(start_date) if start_date else None
        end = parse_datetime(end_date) if end_date else None
        if start and end and end < start:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_CALENDAR_RANGE",
                message="Calendar end date must not be before start date",
            )
        return await self.repository.count_events(
            db,
            organization_id=org_id,
            search=search,
            start=start,
            end=end,
            access=access,
        )

    async def create_calendar_event(
        self, db: AsyncSession, payload: CalendarEventCreatePayload, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        start_time = parse_datetime(payload.start)
        end_time = parse_datetime(payload.end)
        if end_time <= start_time:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_CALENDAR_RANGE",
                message="Calendar event end time must be after its start time",
            )
        event = await self.repository.create_event(
            db,
            data={
                "user_id": current_user.id,
                "organization_id": org_id,
                "title": payload.title,
                "start_time": start_time,
                "end_time": end_time,
                "event_type": payload.event_type or "Meeting",
                "description": payload.description,
            },
        )
        await self._commit(db, "Failed to create calendar event")
        await db.refresh(event)
        return event_to_dict(event)

    async def get_calendar_event(
        self, db: AsyncSession, event_id: str, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access = await record_access_service.resolve(db, current_user, "calendar")
        event = await self.repository.get_event(db, event_id, org_id, access=access)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        return event_to_dict(event)

    async def update_calendar_event(
        self,
        db: AsyncSession,
        event_id: str,
        payload: CalendarEventCreatePayload,
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access = await record_access_service.resolve(db, current_user, "calendar")
        event = await self.repository.get_event(db, event_id, org_id, access=access)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        try:
            if payload.title:
                event.title = payload.title
            if payload.start:
                event.start_time = parse_datetime(payload.start)
            if payload.end:
                event.end_time = parse_datetime(payload.end)
            if event.end_time <= event.start_time:
                raise APIException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    code="INVALID_CALENDAR_RANGE",
                    message="Calendar event end time must be after its start time",
                )
            if payload.event_type:
                event.event_type = payload.event_type
            if payload.description:
                event.description = payload.description
            await db.commit()
            await db.refresh(event)
            return event_to_dict(event)
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to update calendar event",
            ) from e

    async def delete_calendar_event(
        self, db: AsyncSession, event_id: str, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access = await record_access_service.resolve(db, current_user, "calendar")
        event = await self.repository.get_event(db, event_id, org_id, access=access)
        if not event:
            raise NotFoundError(message=f"Calendar event '{event_id}' not found")
        await self.repository.delete_event(db, event)
        await self._commit(db, "Failed to delete calendar event")
        return {"message": f"Event {event_id} deleted successfully", "status": "success"}

    async def get_availability(self, user_id: str | None, date_: str | None) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="CALENDAR_AVAILABILITY_NOT_CONFIGURED",
            message="Calendar availability rules are not configured",
        )

    async def sync_google_calendar(self) -> dict:
        raise APIException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="GOOGLE_CALENDAR_SYNC_NOT_CONFIGURED",
            message="Google Calendar synchronization is not configured",
        )

    async def sync_outlook_calendar(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="OUTLOOK_CALENDAR_NOT_SUPPORTED",
            message="Outlook Calendar synchronization is not supported",
        )

    async def list_recurring_events(self) -> list[dict]:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="RECURRING_CALENDAR_EVENTS_NOT_SUPPORTED",
            message="Recurring calendar events are not supported",
        )

    async def create_recurring_event(self, title: str, rrule: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="RECURRING_CALENDAR_EVENTS_NOT_SUPPORTED",
            message="Recurring calendar events are not supported",
        )


calendar_service = CalendarService()
