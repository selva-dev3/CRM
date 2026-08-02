from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import MeetingResponse, MeetingCreate

router = APIRouter()

@router.get("/", response_model=List[MeetingResponse], summary="List scheduled meetings")
async def list_meetings():
    return [
        {"id": "mtg-1", "title": "Product Demo Call", "start_time": "2026-08-03T14:00:00Z", "end_time": "2026-08-03T14:30:00Z", "attendees": ["john@acme.com"], "meeting_link": "https://zoom.us/j/123456", "ai_summary": "Discussed feature timeline"}
    ]

@router.post("/", response_model=MeetingResponse, status_code=201, summary="Schedule meeting")
async def schedule_meeting(payload: MeetingCreate):
    return {"id": "mtg-2", **payload.model_dump(), "ai_summary": None}
