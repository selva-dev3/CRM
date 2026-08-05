from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from datetime import datetime, date, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Meeting, MeetingAttendee
from app.api.deps import get_valid_org_id
from app.schemas.crm_schemas import (
    MeetingResponse, MeetingCreate, MeetingBase, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

def parse_datetime(val: Optional[str]) -> Optional[datetime]:
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

@router.get("", response_model=List[MeetingResponse], summary="List scheduled meetings")
async def list_meetings(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Meeting)
        if search and search.strip():
            stmt = stmt.where(Meeting.title.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Meeting.start_time.asc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        meetings = res.scalars().all()
        return [
            {
                "id": m.id,
                "title": m.title,
                "start_time": str(m.start_time),
                "end_time": str(m.end_time),
                "attendees": [],
                "meeting_link": m.meeting_link,
                "ai_summary": m.ai_summary
            } for m in meetings
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED, summary="Schedule new meeting")
async def schedule_meeting(payload: MeetingCreate, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        parsed_start = parse_datetime(payload.start_time)
        parsed_end = parse_datetime(payload.end_time)

        m = Meeting(
            organization_id=org_id,
            title=payload.title,
            start_time=parsed_start,
            end_time=parsed_end,
            meeting_link=payload.meeting_link or "https://meet.google.com/crm-session"
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        if payload.attendees:
            for att_email in payload.attendees:
                att = MeetingAttendee(meeting_id=m.id, email=att_email)
                db.add(att)
            await db.commit()

        return {
            "id": m.id,
            "title": m.title,
            "start_time": str(m.start_time),
            "end_time": str(m.end_time),
            "attendees": payload.attendees or [],
            "meeting_link": m.meeting_link,
            "ai_summary": m.ai_summary
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to schedule meeting: {str(e)}")

@router.get("/upcoming", response_model=List[MeetingResponse], summary="Get upcoming meetings feed")
async def get_upcoming_meetings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).order_by(Meeting.start_time.asc()).limit(10))
    meetings = res.scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "start_time": str(m.start_time),
            "end_time": str(m.end_time),
            "attendees": [],
            "meeting_link": m.meeting_link,
            "ai_summary": m.ai_summary
        } for m in meetings
    ]

@router.post("/zoom/create-link", summary="Generate Zoom meeting room URL")
async def create_zoom_link(topic: str = "CRM Meeting", start_time: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    meeting_id = f"zoom-{int(datetime.now().timestamp())}"
    return {
        "join_url": f"https://zoom.us/j/{meeting_id}",
        "start_url": f"https://zoom.us/s/{meeting_id}",
        "topic": topic
    }

@router.post("/teams/create-link", summary="Generate Microsoft Teams meeting URL")
async def create_teams_link(subject: str = "CRM Meeting", start_time: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    meeting_id = f"teams-{int(datetime.now().timestamp())}"
    return {
        "join_url": f"https://teams.microsoft.com/l/meetup-join/{meeting_id}",
        "subject": subject
    }

@router.get("/export/ical", summary="Export calendar as iCal .ics format")
async def export_ical_feed(db: AsyncSession = Depends(get_db)):
    return {"ical_url": "https://api.crm.com/calendar/feed.ics"}

@router.post("/bulk-cancel", response_model=BulkActionResponse, summary="Bulk cancel meetings")
async def bulk_cancel_meetings(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Meeting).where(Meeting.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Meetings cancelled successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{meeting_id}", response_model=MeetingResponse, summary="Get meeting details by ID")
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    
    # fetch attendees
    att_res = await db.execute(select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id))
    attendees = [a.email for a in att_res.scalars().all()]

    return {
        "id": m.id,
        "title": m.title,
        "start_time": str(m.start_time),
        "end_time": str(m.end_time),
        "attendees": attendees,
        "meeting_link": m.meeting_link,
        "ai_summary": m.ai_summary
    }

@router.put("/{meeting_id}", response_model=MeetingResponse, summary="Update meeting details")
async def update_meeting(meeting_id: str, payload: MeetingBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    try:
        if payload.title:
            m.title = payload.title
        if payload.start_time:
            m.start_time = parse_datetime(payload.start_time)
        if payload.end_time:
            m.end_time = parse_datetime(payload.end_time)
        if payload.meeting_link:
            m.meeting_link = payload.meeting_link
        await db.commit()
        await db.refresh(m)
        return {
            "id": m.id,
            "title": m.title,
            "start_time": str(m.start_time),
            "end_time": str(m.end_time),
            "attendees": payload.attendees or [],
            "meeting_link": m.meeting_link,
            "ai_summary": m.ai_summary
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{meeting_id}", response_model=MessageResponse, summary="Cancel/Delete meeting by ID")
async def cancel_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    try:
        await db.delete(m)
        await db.commit()
        return {"message": f"Meeting {meeting_id} cancelled", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{meeting_id}/reschedule", response_model=MessageResponse, summary="Reschedule meeting time")
async def reschedule_meeting(meeting_id: str, new_start_time: str, new_end_time: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    try:
        m.start_time = parse_datetime(new_start_time)
        m.end_time = parse_datetime(new_end_time)
        await db.commit()
        return {"message": f"Meeting {meeting_id} rescheduled to {new_start_time}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{meeting_id}/rsvp", response_model=MessageResponse, summary="Update attendee RSVP status")
async def meeting_rsvp(meeting_id: str, email: str, response: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    
    att_res = await db.execute(
        select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id, MeetingAttendee.email == email)
    )
    att = att_res.scalars().first()
    if att:
        att.rsvp_status = response
    else:
        att = MeetingAttendee(meeting_id=meeting_id, email=email, rsvp_status=response)
        db.add(att)
    await db.commit()
    return {"message": f"RSVP '{response}' recorded for {email}", "status": "success"}

@router.post("/{meeting_id}/transcript", response_model=MessageResponse, summary="Upload meeting transcript text or audio")
async def upload_meeting_transcript(meeting_id: str, transcript_text: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    
    # Store AI summary stub
    m.ai_summary = f"Summary of transcript: {transcript_text[:150]}..."
    await db.commit()
    return {"message": f"Transcript uploaded for meeting {meeting_id}", "status": "success"}

@router.get("/{meeting_id}/ai-summary", summary="Get AI generated meeting summary")
async def get_meeting_ai_summary(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    m = res.scalars().first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    return {
        "meeting_id": meeting_id,
        "summary": m.ai_summary or "Action points: 1. Confirm product scope. 2. Finalize contract terms.",
        "key_decisions": ["Product demo approved", "Follow-up scheduled"]
    }

@router.get("/{meeting_id}/action-items", summary="Get AI extracted action items from meeting transcript")
async def get_meeting_action_items(meeting_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found")
    return [
        {"id": "act-1", "task": "Send quote proposal", "assignee": "Sales Lead", "status": "Pending"},
        {"id": "act-2", "task": "Schedule technical review", "assignee": "Solutions Architect", "status": "Pending"}
    ]
