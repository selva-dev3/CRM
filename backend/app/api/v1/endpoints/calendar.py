from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import CalendarEvent

router = APIRouter()

@router.get("/events", response_model=List[CalendarEvent], summary="Get synchronized calendar events")
async def get_calendar_events():
    return [
        {"id": "evt-1", "title": "Client Sync - TechCorp", "start": "2026-08-03T10:00:00Z", "end": "2026-08-03T11:00:00Z", "event_type": "Meeting"}
    ]
