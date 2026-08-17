from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MeetingBase,
    MeetingCreate,
    MeetingResponse,
    MessageResponse,
)
from app.services.meeting_service import meeting_service

router = APIRouter()


@router.get("", response_model=List[MeetingResponse], summary="List scheduled meetings", dependencies=[Depends(require_permission("meetings:read"))])
async def list_meetings(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await meeting_service.list_meetings(db, page=page, limit=limit, search=search)


@router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule new meeting",
    dependencies=[Depends(require_permission("meetings:create"))],
)
async def schedule_meeting(
    payload: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await meeting_service.schedule_meeting(db, payload, current_user)


@router.get("/upcoming", response_model=List[MeetingResponse], summary="Get upcoming meetings feed", dependencies=[Depends(require_permission("meetings:read"))])
async def get_upcoming_meetings(db: AsyncSession = Depends(get_db)):
    return await meeting_service.get_upcoming_meetings(db)


@router.post("/zoom/create-link", summary="Generate Zoom meeting room URL", dependencies=[Depends(require_permission("meetings:create"))])
async def create_zoom_link(topic: str = "CRM Meeting", start_time: Optional[str] = None):
    return await meeting_service.create_zoom_link(topic)


@router.post("/teams/create-link", summary="Generate Microsoft Teams meeting URL", dependencies=[Depends(require_permission("meetings:create"))])
async def create_teams_link(subject: str = "CRM Meeting", start_time: Optional[str] = None):
    return await meeting_service.create_teams_link(subject)


@router.get("/export/ical", summary="Export calendar as iCal .ics format", dependencies=[Depends(require_permission("meetings:read"))])
async def export_ical_feed(db: AsyncSession = Depends(get_db)):
    return await meeting_service.export_ical()


@router.post("/bulk-cancel", response_model=BulkActionResponse, summary="Bulk cancel meetings", dependencies=[Depends(require_permission("meetings:delete"))])
async def bulk_cancel_meetings(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await meeting_service.bulk_cancel(db, payload.ids)


@router.get("/{meeting_id}", response_model=MeetingResponse, summary="Get meeting details by ID", dependencies=[Depends(require_permission("meetings:read"))])
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return await meeting_service.get_meeting(db, meeting_id)


@router.put("/{meeting_id}", response_model=MeetingResponse, summary="Update meeting details", dependencies=[Depends(require_permission("meetings:update"))])
async def update_meeting(meeting_id: str, payload: MeetingBase, db: AsyncSession = Depends(get_db)):
    return await meeting_service.update_meeting(db, meeting_id, payload)


@router.delete("/{meeting_id}", response_model=MessageResponse, summary="Cancel/Delete meeting by ID", dependencies=[Depends(require_permission("meetings:delete"))])
async def cancel_meeting(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return await meeting_service.cancel_meeting(db, meeting_id)


@router.post("/{meeting_id}/reschedule", response_model=MessageResponse, summary="Reschedule meeting time", dependencies=[Depends(require_permission("meetings:update"))])
async def reschedule_meeting(
    meeting_id: str, new_start_time: str, new_end_time: str, db: AsyncSession = Depends(get_db)
):
    return await meeting_service.reschedule_meeting(db, meeting_id, new_start_time, new_end_time)


@router.post("/{meeting_id}/rsvp", response_model=MessageResponse, summary="Update attendee RSVP status", dependencies=[Depends(require_permission("meetings:invite"))])
async def meeting_rsvp(meeting_id: str, email: str, response: str, db: AsyncSession = Depends(get_db)):
    return await meeting_service.rsvp(db, meeting_id, email, response)


@router.post("/{meeting_id}/transcript", response_model=MessageResponse, summary="Upload meeting transcript text or audio", dependencies=[Depends(require_permission("meetings:update"))])
async def upload_meeting_transcript(
    meeting_id: str, transcript_text: str, db: AsyncSession = Depends(get_db)
):
    return await meeting_service.upload_transcript(db, meeting_id, transcript_text)


@router.get("/{meeting_id}/ai-summary", summary="Get AI generated meeting summary", dependencies=[Depends(require_permission("meetings:read"))])
async def get_meeting_ai_summary(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return await meeting_service.get_ai_summary(db, meeting_id)


@router.get("/{meeting_id}/action-items", summary="Get AI extracted action items from meeting transcript", dependencies=[Depends(require_permission("meetings:read"))])
async def get_meeting_action_items(meeting_id: str, db: AsyncSession = Depends(get_db)):
    return await meeting_service.get_action_items(db, meeting_id)