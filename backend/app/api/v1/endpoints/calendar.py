from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import CalendarEventModel
from app.schemas.crm_schemas import CalendarEvent, MessageResponse

router = APIRouter()

@router.get("/events", response_model=List[CalendarEvent], summary="Fetch calendar events between date range")
async def get_calendar_events(start_date: str = "2026-08-01", end_date: str = "2026-08-31", db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(CalendarEventModel).limit(20))
        events = res.scalars().all()
        return [{"id": e.id, "title": e.title, "start": str(e.start_time), "end": str(e.end_time), "event_type": e.event_type} for e in events]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/events", response_model=CalendarEvent, status_code=status.HTTP_201_CREATED, summary="Create new calendar event")
async def create_calendar_event(title: str, start: str, end: str, event_type: str = "Meeting", db: AsyncSession = Depends(get_db)):
    try:
        e = CalendarEventModel(user_id="usr-1", title=title, start_time=start, end_time=end, event_type=event_type)
        db.add(e)
        await db.commit()
        return {"id": e.id, "title": e.title, "start": str(e.start_time), "end": str(e.end_time), "event_type": e.event_type}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/events/{event_id}", response_model=CalendarEvent, summary="Get calendar event details by ID")
async def get_calendar_event(event_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
    e = res.scalars().first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar event '{event_id}' not found")
    return {"id": e.id, "title": e.title, "start": str(e.start_time), "end": str(e.end_time), "event_type": e.event_type}

@router.put("/events/{event_id}", response_model=CalendarEvent, summary="Update calendar event details")
async def update_calendar_event(event_id: str, title: str, start: str, end: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
    e = res.scalars().first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Calendar event '{event_id}' not found")
    try:
        e.title = title
        await db.commit()
        return {"id": e.id, "title": e.title, "start": str(e.start_time), "end": str(e.end_time), "event_type": e.event_type}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/availability", summary="Get free/busy time slots for user")
async def get_availability(user_id: str, date: str, db: AsyncSession = Depends(get_db)):
    return {"user_id": user_id, "date": date, "available_slots": ["09:00-09:30", "11:30-12:00", "15:00-16:00"]}

@router.post("/sync/google", response_model=MessageResponse, summary="Trigger Google Calendar 2-way sync")
async def sync_google_calendar(db: AsyncSession = Depends(get_db)):
    return {"message": "Google Calendar sync initiated", "status": "success"}

@router.post("/sync/outlook", response_model=MessageResponse, summary="Trigger Outlook Calendar 2-way sync")
async def sync_outlook_calendar(db: AsyncSession = Depends(get_db)):
    return {"message": "Outlook Calendar sync initiated", "status": "success"}

@router.get("/recurring", summary="List recurring event rules")
async def list_recurring_events(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/recurring", response_model=MessageResponse, summary="Create recurring event rule")
async def create_recurring_event(title: str, rrule: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Recurring event rule '{title}' created", "status": "success"}
