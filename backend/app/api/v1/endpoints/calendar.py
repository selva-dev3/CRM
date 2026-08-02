from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import CalendarEvent, MessageResponse

router = APIRouter()

@router.get("/events", response_model=List[CalendarEvent], summary="Fetch calendar events between date range")
async def get_calendar_events(start_date: str = "2026-08-01", end_date: str = "2026-08-31"):
    return [
        {"id": "evt-1", "title": "Client Onboarding Call", "start": "2026-08-03T10:00:00Z", "end": "2026-08-03T11:00:00Z", "event_type": "Meeting"},
        {"id": "evt-2", "title": "Q3 Sales Strategy Sync", "start": "2026-08-05T14:00:00Z", "end": "2026-08-05T15:30:00Z", "event_type": "Internal"}
    ]

@router.post("/events", response_model=CalendarEvent, status_code=status.HTTP_201_CREATED, summary="Create new calendar event")
async def create_calendar_event(title: str, start: str, end: str, event_type: str = "Meeting"):
    return {"id": "evt-3", "title": title, "start": start, "end": end, "event_type": event_type}

@router.get("/events/{event_id}", response_model=CalendarEvent, summary="Get calendar event details by ID")
async def get_calendar_event(event_id: str):
    return {"id": event_id, "title": "Client Onboarding Call", "start": "2026-08-03T10:00:00Z", "end": "2026-08-03T11:00:00Z", "event_type": "Meeting"}

@router.put("/events/{event_id}", response_model=CalendarEvent, summary="Update calendar event details")
async def update_calendar_event(event_id: str, title: str, start: str, end: str):
    return {"id": event_id, "title": title, "start": start, "end": end, "event_type": "Meeting"}

@router.delete("/events/{event_id}", response_model=MessageResponse, summary="Delete calendar event by ID")
async def delete_calendar_event(event_id: str):
    return {"message": f"Event {event_id} deleted", "status": "success"}

@router.get("/availability", summary="Get free/busy time slots for user")
async def get_availability(user_id: str, date: str):
    return {"user_id": user_id, "date": date, "available_slots": ["09:00-09:30", "11:30-12:00", "15:00-16:00"]}

@router.post("/sync/google", response_model=MessageResponse, summary="Trigger Google Calendar 2-way sync")
async def sync_google_calendar():
    return {"message": "Google Calendar sync initiated", "status": "success"}

@router.post("/sync/outlook", response_model=MessageResponse, summary="Trigger Outlook Calendar 2-way sync")
async def sync_outlook_calendar():
    return {"message": "Outlook Calendar sync initiated", "status": "success"}

@router.get("/recurring", summary="List recurring event rules")
async def list_recurring_events():
    return [{"id": "rec-1", "title": "Weekly Sales Standup", "rrule": "FREQ=WEEKLY;BYDAY=MO"}]

@router.post("/recurring", response_model=MessageResponse, summary="Create recurring event rule")
async def create_recurring_event(title: str, rrule: str):
    return {"message": f"Recurring event rule '{title}' created", "status": "success"}
