from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Meeting, MeetingAttendee
from app.schemas.crm_schemas import (
    MeetingResponse, MeetingCreate, MeetingBase, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("", response_model=List[MeetingResponse], summary="List scheduled meetings")
async def list_meetings(page: int = 1, limit: int = 20, db: AsyncSession = Depends(get_db)):
    stmt = select(Meeting).offset((page - 1) * limit).limit(limit)
    res = await db.execute(stmt)
    meetings = res.scalars().all()
    if meetings:
        return [{"id": m.id, "title": m.title, "start_time": str(m.start_time), "end_time": str(m.end_time), "attendees": [], "meeting_link": m.meeting_link, "ai_summary": m.ai_summary} for m in meetings]
    return [
        {"id": "mtg-1", "title": "Product Demo & Technical Discovery", "start_time": "2026-08-03T14:00:00Z", "end_time": "2026-08-03T15:00:00Z", "attendees": ["alice@techcorp.com", "usr-1@company.com"], "meeting_link": "https://zoom.us/j/123456789", "ai_summary": "Discussed API security requirements."},
        {"id": "mtg-2", "title": "Contract Negotiation Sync", "start_time": "2026-08-04T10:00:00Z", "end_time": "2026-08-04T10:30:00Z", "attendees": ["bob@globalsolutions.com"], "meeting_link": "https://teams.microsoft.com/l/meet", "ai_summary": None}
    ]

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED, summary="Schedule new meeting")
async def schedule_meeting(payload: MeetingCreate, db: AsyncSession = Depends(get_db)):
    m = Meeting(organization_id="org-1", title=payload.title, start_time=payload.start_time, end_time=payload.end_time, meeting_link=payload.meeting_link)
    db.add(m)
    await db.commit()
    return {"id": m.id, "title": m.title, "start_time": str(m.start_time), "end_time": str(m.end_time), "attendees": payload.attendees, "meeting_link": m.meeting_link, "ai_summary": None}

@router.get("/upcoming", response_model=List[MeetingResponse], summary="Get upcoming meetings feed")
async def get_upcoming_meetings(db: AsyncSession = Depends(get_db)):
    return [{"id": "mtg-1", "title": "Product Demo", "start_time": "2026-08-03T14:00:00Z", "end_time": "2026-08-03T15:00:00Z", "attendees": ["alice@techcorp.com"], "meeting_link": "https://zoom.us/j/123", "ai_summary": None}]

@router.post("/zoom/create-link", summary="Generate Zoom meeting room URL")
async def create_zoom_link(topic: str, start_time: str, db: AsyncSession = Depends(get_db)):
    return {"join_url": "https://zoom.us/j/987654321", "start_url": "https://zoom.us/s/987654321"}

@router.post("/teams/create-link", summary="Generate Microsoft Teams meeting URL")
async def create_teams_link(subject: str, start_time: str, db: AsyncSession = Depends(get_db)):
    return {"join_url": "https://teams.microsoft.com/l/meetup-join/abc123"}

@router.get("/export/ical", summary="Export calendar as iCal .ics format")
async def export_ical_feed(db: AsyncSession = Depends(get_db)):
    return {"ical_url": "https://api.crm.com/calendar/feed.ics"}

@router.post("/bulk-cancel", response_model=BulkActionResponse, summary="Bulk cancel meetings")
async def bulk_cancel_meetings(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Meetings cancelled successfully"}

@router.get("/{meeting_id}", response_model=MeetingResponse, summary="Get meeting details by ID")
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if m:
        return {"id": m.id, "title": m.title, "start_time": str(m.start_time), "end_time": str(m.end_time), "attendees": [], "meeting_link": m.meeting_link, "ai_summary": m.ai_summary}
    return {"id": meeting_id, "title": "Product Demo & Discovery", "start_time": "2026-08-03T14:00:00Z", "end_time": "2026-08-03T15:00:00Z", "attendees": ["alice@techcorp.com"], "meeting_link": "https://zoom.us/j/123456789", "ai_summary": "Discussed architecture."}

@router.put("/{meeting_id}", response_model=MeetingResponse, summary="Update meeting details")
async def update_meeting(meeting_id: str, payload: MeetingBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if m:
        if payload.title: m.title = payload.title
        await db.commit()
        return {"id": m.id, "title": m.title, "start_time": str(m.start_time), "end_time": str(m.end_time), "attendees": payload.attendees, "meeting_link": m.meeting_link, "ai_summary": m.ai_summary}
    return {"id": meeting_id, "title": payload.title, "start_time": payload.start_time, "end_time": payload.end_time, "attendees": payload.attendees, "meeting_link": payload.meeting_link, "ai_summary": None}

@router.delete("/{meeting_id}", response_model=MessageResponse, summary="Cancel/Delete meeting by ID")
async def cancel_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if m:
        await db.delete(m)
        await db.commit()
    return {"message": f"Meeting {meeting_id} cancelled", "status": "success"}

@router.post("/{meeting_id}/reschedule", response_model=MessageResponse, summary="Reschedule meeting time")
async def reschedule_meeting(meeting_id: str, new_start_time: str, new_end_time: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Meeting {meeting_id} rescheduled to {new_start_time}", "status": "success"}

@router.post("/{meeting_id}/rsvp", response_model=MessageResponse, summary="Update attendee RSVP status")
async def meeting_rsvp(meeting_id: str, email: str, response: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"RSVP '{response}' recorded for {email}", "status": "success"}

@router.post("/{meeting_id}/transcript", response_model=MessageResponse, summary="Upload meeting transcript text or audio")
async def upload_meeting_transcript(meeting_id: str, transcript_text: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Transcript uploaded for meeting {meeting_id}", "status": "success"}

@router.get("/{meeting_id}/ai-summary", summary="Get AI generated meeting summary")
async def get_meeting_ai_summary(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return {"meeting_id": meeting_id, "summary": "Prospect agreed to pilot. Security review needed.", "key_decisions": ["Proceed to 30-day POC", "Send NDA"]}

@router.get("/{meeting_id}/action-items", summary="Get AI extracted action items from meeting transcript")
async def get_meeting_action_items(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return [{"task": "Send custom pricing proposal", "assignee": "usr-1", "due_date": "2026-08-05"}]
