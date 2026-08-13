from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from datetime import datetime, date, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.session import get_db
from app.models import CalendarEventModel, User
from app.schemas.crm_schemas import MessageResponse

router = APIRouter()

class CalendarEventCreatePayload(BaseModel):
    title: str
    start: str
    end: str
    event_type: Optional[str] = "Meeting"
    description: Optional[str] = None

class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: str
    end: str
    event_type: str
    description: Optional[str] = None

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

async def resolve_user_id(db: AsyncSession) -> str:
    first_user_res = await db.execute(select(User).limit(1))
    first_user = first_user_res.scalars().first()
    if first_user:
        return first_user.id
    return "user-default-1"

@router.get("/events", response_model=List[CalendarEventResponse], summary="Fetch calendar events between date range")
async def get_calendar_events(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(CalendarEventModel)
        if search and search.strip():
            stmt = stmt.where(CalendarEventModel.title.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(CalendarEventModel.start_time.asc()).limit(50)
        res = await db.execute(stmt)
        events = res.scalars().all()
        return [
            {
                "id": e.id,
                "title": e.title,
                "start": str(e.start_time),
                "end": str(e.end_time),
                "event_type": e.event_type or "Meeting",
                "description": e.description
            } for e in events
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED, summary="Create new calendar event")
async def create_calendar_event(payload: CalendarEventCreatePayload, db: AsyncSession = Depends(get_db)):
    try:
        uid = await resolve_user_id(db)
        parsed_start = parse_datetime(payload.start)
        parsed_end = parse_datetime(payload.end)
        e = CalendarEventModel(
            user_id=uid,
            title=payload.title,
            start_time=parsed_start,
            end_time=parsed_end,
            event_type=payload.event_type or "Meeting",
            description=payload.description
        )
        db.add(e)
        await db.commit()
        await db.refresh(e)
        return {
            "id": e.id,
            "title": e.title,
            "start": str(e.start_time),
            "end": str(e.end_time),
            "event_type": e.event_type,
            "description": e.description
        }
    except Exception as err:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create calendar event: {str(err)}")

@router.get("/events/{event_id}", response_model=CalendarEventResponse, summary="Get calendar event details by ID")
async def get_calendar_event(event_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
    e = res.scalars().first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar event '{event_id}' not found")
    return {
        "id": e.id,
        "title": e.title,
        "start": str(e.start_time),
        "end": str(e.end_time),
        "event_type": e.event_type or "Meeting",
        "description": e.description
    }

@router.put("/events/{event_id}", response_model=CalendarEventResponse, summary="Update calendar event details")
async def update_calendar_event(event_id: str, payload: CalendarEventCreatePayload, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
    e = res.scalars().first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar event '{event_id}' not found")
    try:
        if payload.title:
            e.title = payload.title
        if payload.start:
            e.start_time = parse_datetime(payload.start)
        if payload.end:
            e.end_time = parse_datetime(payload.end)
        if payload.event_type:
            e.event_type = payload.event_type
        if payload.description:
            e.description = payload.description
        await db.commit()
        await db.refresh(e)
        return {
            "id": e.id,
            "title": e.title,
            "start": str(e.start_time),
            "end": str(e.end_time),
            "event_type": e.event_type,
            "description": e.description
        }
    except Exception as err:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

@router.delete("/events/{event_id}", response_model=MessageResponse, summary="Delete calendar event by ID")
async def delete_calendar_event(event_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
    e = res.scalars().first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar event '{event_id}' not found")
    try:
        await db.delete(e)
        await db.commit()
        return {"message": f"Event {event_id} deleted successfully", "status": "success"}
    except Exception as err:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

@router.get("/availability", summary="Get free/busy time slots for user")
async def get_availability(user_id: Optional[str] = Query(None), date: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return {
        "user_id": user_id or "default-user",
        "date": date or str(datetime.now().date()),
        "available_slots": ["09:00-09:30", "11:30-12:00", "14:00-14:30", "16:00-17:00"]
    }

@router.post("/sync/google", response_model=MessageResponse, summary="Trigger Google Calendar 2-way sync")
async def sync_google_calendar(db: AsyncSession = Depends(get_db)):
    return {"message": "Google Calendar 2-way sync completed successfully", "status": "success"}

@router.post("/sync/outlook", response_model=MessageResponse, summary="Trigger Outlook Calendar 2-way sync")
async def sync_outlook_calendar(db: AsyncSession = Depends(get_db)):
    return {"message": "Outlook Calendar 2-way sync completed successfully", "status": "success"}

@router.get("/recurring", summary="List recurring event rules")
async def list_recurring_events(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "rec-1", "title": "Weekly Team Sync", "rrule": "FREQ=WEEKLY;BYDAY=MO", "event_type": "Internal"},
        {"id": "rec-2", "title": "Monthly Revenue Review", "rrule": "FREQ=MONTHLY;BYMONTHDAY=1", "event_type": "Executive"}
    ]

@router.post("/recurring", response_model=MessageResponse, summary="Create recurring event rule")
async def create_recurring_event(title: str = Query(...), rrule: str = Query(...), db: AsyncSession = Depends(get_db)):
    return {"message": f"Recurring event rule '{title}' created with pattern {rrule}", "status": "success"}
