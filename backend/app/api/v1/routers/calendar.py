from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    CalendarEventCreatePayload,
    CalendarEventResponse,
    MessageResponse,
)
from app.services.calendar_service import calendar_service

router = APIRouter()


@router.get(
    "/events",
    response_model=list[CalendarEventResponse],
    summary="Fetch calendar events between date range",
    dependencies=[Depends(require_permission("calendar:read"))],
)
async def get_calendar_events(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await calendar_service.get_calendar_events(
        db, search=search, current_user=current_user
    )


@router.post(
    "/events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new calendar event",
    dependencies=[Depends(require_permission("calendar:write"))],
)
async def create_calendar_event(
    payload: CalendarEventCreatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await calendar_service.create_calendar_event(db, payload, current_user)


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
    summary="Get calendar event details by ID",
    dependencies=[Depends(require_permission("calendar:read"))],
)
async def get_calendar_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await calendar_service.get_calendar_event(db, event_id, current_user)


@router.put(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
    summary="Update calendar event details",
    dependencies=[Depends(require_permission("calendar:write"))],
)
async def update_calendar_event(
    event_id: str,
    payload: CalendarEventCreatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await calendar_service.update_calendar_event(db, event_id, payload, current_user)


@router.delete(
    "/events/{event_id}",
    response_model=MessageResponse,
    summary="Delete calendar event by ID",
    dependencies=[Depends(require_permission("calendar:write"))],
)
async def delete_calendar_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await calendar_service.delete_calendar_event(db, event_id, current_user)


@router.get(
    "/availability",
    summary="Get free/busy time slots for user",
    dependencies=[Depends(require_permission("calendar:sync"))],
)
async def get_availability(
    user_id: str | None = Query(None),
    date: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await calendar_service.get_availability(user_id, date)


@router.post(
    "/sync/google",
    response_model=MessageResponse,
    summary="Trigger Google Calendar 2-way sync",
    dependencies=[Depends(require_permission("calendar:sync"))],
)
async def sync_google_calendar(db: AsyncSession = Depends(get_db)):
    return await calendar_service.sync_google_calendar()


@router.post(
    "/sync/outlook",
    response_model=MessageResponse,
    summary="Trigger Outlook Calendar 2-way sync",
    dependencies=[Depends(require_permission("calendar:sync"))],
)
async def sync_outlook_calendar(db: AsyncSession = Depends(get_db)):
    return await calendar_service.sync_outlook_calendar()


@router.get(
    "/recurring",
    summary="List recurring event rules",
    dependencies=[Depends(require_permission("calendar:read"))],
)
async def list_recurring_events(db: AsyncSession = Depends(get_db)):
    return await calendar_service.list_recurring_events()


@router.post(
    "/recurring",
    response_model=MessageResponse,
    summary="Create recurring event rule",
    dependencies=[Depends(require_permission("calendar:write"))],
)
async def create_recurring_event(
    title: str = Query(...),
    rrule: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await calendar_service.create_recurring_event(title, rrule)
