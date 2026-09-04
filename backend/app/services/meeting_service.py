from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Meeting, User
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.crm_schemas import MeetingBase, MeetingCreate
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def parse_datetime(val: str | None) -> datetime:
    if not val or not str(val).strip():
        return datetime.now(UTC)
    val_str = str(val).strip()
    try:
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except Exception:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except Exception:
            return datetime.now(UTC)


def meeting_to_dict(meeting: Meeting, attendees: list[str] | None = None) -> dict:
    return {
        "id": meeting.id,
        "title": meeting.title,
        "start_time": str(meeting.start_time),
        "end_time": str(meeting.end_time),
        "attendees": attendees or [],
        "meeting_link": meeting.meeting_link,
        "location": getattr(meeting, "location", None),
        "ai_summary": meeting.ai_summary,
        "created_at": str(meeting.created_at) if meeting.created_at else None,
    }


class MeetingService:
    """Business logic for the Meeting domain."""

    def __init__(
        self,
        repository: MeetingRepository | None = None,
        ai_service_instance: AIDomainService | None = None,
    ) -> None:
        self.repository = repository or MeetingRepository()
        self.ai_service = ai_service_instance or ai_domain_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_meetings(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> list[dict]:
        meetings = await self.repository.list(db, page=page, limit=limit, search=search)
        return [meeting_to_dict(m) for m in meetings]

    async def get_meeting(self, db: AsyncSession, meeting_id: str) -> dict:
        meeting = await self.repository.get_by_id(db, meeting_id)
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        attendees = await self.repository.list_attendee_emails(db, meeting_id)
        return meeting_to_dict(meeting, attendees)

    async def schedule_meeting(
        self, db: AsyncSession, payload: MeetingCreate, current_user: User | None = None
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "start_time": parse_datetime(payload.start_time),
            "end_time": parse_datetime(payload.end_time),
            "meeting_link": payload.meeting_link or "https://meet.google.com/crm-session",
        }
        meeting = await self.repository.create(db, data=data)
        await self._commit(db, "Failed to schedule meeting")
        await db.refresh(meeting)
        attendee_emails = list(getattr(payload, "attendee_emails", None) or [])
        if attendee_emails:
            for att_email in attendee_emails:
                await self.repository.create_attendee(db, meeting_id=meeting.id, email=att_email)
            await self._commit(db, "Failed to save meeting attendees")
        await notification_service.notify(
            db,
            event_name="meeting.created",
            organization_id=meeting.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="meeting",
            entity_id=meeting.id,
            data={
                "id": meeting.id,
                "title": meeting.title,
                "start_time": str(meeting.start_time),
                "end_time": str(meeting.end_time),
                "location": getattr(meeting, "location", None),
                "meeting_link": meeting.meeting_link,
                "attendees": attendee_emails,
            },
        )
        return meeting_to_dict(meeting, attendee_emails)

    async def get_upcoming_meetings(self, db: AsyncSession) -> list[dict]:
        meetings = await self.repository.list_upcoming(db)
        return [meeting_to_dict(m) for m in meetings]

    async def bulk_cancel(self, db: AsyncSession, ids: list[str]) -> dict:
        meetings = await self.repository.list_by_ids(db, ids)
        for meeting in meetings:
            await self.repository.delete(db, meeting)
        await self._commit(db, "Failed to cancel meetings")
        return {"affected_count": len(meetings), "message": "Meetings cancelled successfully"}

    async def update_meeting(self, db: AsyncSession, meeting_id: str, payload: MeetingBase) -> dict:
        meeting = await self.repository.get_by_id(db, meeting_id)
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        if payload.title:
            meeting.title = payload.title
        if payload.start_time:
            meeting.start_time = parse_datetime(payload.start_time)
        if payload.end_time:
            meeting.end_time = parse_datetime(payload.end_time)
        if payload.meeting_link:
            meeting.meeting_link = payload.meeting_link
        await self._commit(db, "Failed to update meeting")
        await db.refresh(meeting)
        attendees = await self.repository.list_attendee_emails(db, meeting_id)
        return meeting_to_dict(meeting, attendees)

    async def cancel_meeting(self, db: AsyncSession, meeting_id: str) -> dict:
        meeting = await self.repository.get_by_id(db, meeting_id)
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        await self.repository.delete(db, meeting)
        await self._commit(db, "Failed to cancel meeting")
        return {"message": f"Meeting {meeting_id} cancelled", "status": "success"}

    async def reschedule_meeting(
        self, db: AsyncSession, meeting_id: str, new_start_time: str, new_end_time: str
    ) -> dict:
        meeting = await self.repository.get_by_id(db, meeting_id)
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        meeting.start_time = parse_datetime(new_start_time)
        meeting.end_time = parse_datetime(new_end_time)
        await self._commit(db, "Failed to reschedule meeting")
        return {
            "message": f"Meeting {meeting_id} rescheduled to {new_start_time}",
            "status": "success",
        }

    async def rsvp(self, db: AsyncSession, meeting_id: str, email: str, response: str) -> dict:
        meeting = await self.repository.get_by_id(db, meeting_id)
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        attendee = await self.repository.get_attendee(db, meeting_id=meeting_id, email=email)
        if attendee:
            attendee.rsvp_status = response
        else:
            await self.repository.create_attendee(
                db, meeting_id=meeting_id, email=email, rsvp_status=response
            )
        await self._commit(db, "Failed to record RSVP")
        return {"message": f"RSVP '{response}' recorded for {email}", "status": "success"}

    async def upload_transcript(
        self,
        db: AsyncSession,
        meeting_id: str,
        transcript_text: str,
        current_user: User,
    ) -> dict:
        await self.ai_service.analyze_meeting(db, meeting_id, transcript_text, current_user)
        return {"message": f"Transcript uploaded for meeting {meeting_id}", "status": "success"}

    async def get_ai_summary(self, db: AsyncSession, meeting_id: str, current_user: User) -> dict:
        meeting = await self.repository.get_by_id_scoped(
            db,
            meeting_id=meeting_id,
            organization_id=current_user.organization_id or "",
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        intelligence = await self.ai_service.get_meeting_intelligence(db, meeting.id, current_user)
        return {
            "meeting_id": meeting_id,
            "summary": meeting.ai_summary,
            "key_decisions": intelligence.decisions if intelligence else [],
        }

    async def get_action_items(
        self, db: AsyncSession, meeting_id: str, current_user: User
    ) -> list[dict]:
        meeting = await self.repository.get_by_id_scoped(
            db,
            meeting_id=meeting_id,
            organization_id=current_user.organization_id or "",
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        summary = await self.ai_service.get_meeting_intelligence(db, meeting.id, current_user)
        if not summary:
            return []
        return [
            {
                "id": f"{meeting.id}:{index}",
                "task": item,
                "assignee": None,
                "status": "Proposed",
            }
            for index, item in enumerate(summary.action_items, start=1)
        ]

    async def create_zoom_link(self, topic: str) -> dict:
        meeting_id = f"zoom-{int(datetime.now().timestamp())}"
        return {
            "join_url": f"https://zoom.us/j/{meeting_id}",
            "start_url": f"https://zoom.us/s/{meeting_id}",
            "topic": topic,
        }

    async def create_teams_link(self, subject: str) -> dict:
        meeting_id = f"teams-{int(datetime.now().timestamp())}"
        return {
            "join_url": f"https://teams.microsoft.com/l/meetup-join/{meeting_id}",
            "subject": subject,
        }

    async def export_ical(self) -> dict:
        return {"ical_url": "https://api.crm.com/calendar/feed.ics"}


meeting_service = MeetingService()
