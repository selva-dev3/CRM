from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Meeting, User
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.crm_schemas import MeetingCreate, MeetingUpdate
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def parse_datetime(val: str | None) -> datetime:
    if not val or not str(val).strip():
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="MEETING_DATETIME_REQUIRED",
            message="Meeting date and time are required",
        )
    val_str = str(val).strip()
    try:
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except ValueError as exc:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_MEETING_DATETIME",
                message="Meeting date and time must be valid ISO-8601 values",
            ) from exc


def meeting_to_dict(meeting: Meeting, attendees: list[str] | None = None) -> dict:
    return {
        "id": meeting.id,
        "title": meeting.title,
        "start_time": str(meeting.start_time),
        "end_time": str(meeting.end_time),
        "attendees": attendees or [],
        "meeting_link": meeting.meeting_link,
        "location": getattr(meeting, "location", None),
        "status": meeting.status,
        "lead_id": meeting.lead_id,
        "contact_id": meeting.contact_id,
        "company_id": meeting.company_id,
        "deal_id": meeting.deal_id,
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
        organization_id: str,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> list[dict]:
        meetings = await self.repository.list(
            db,
            page=page,
            limit=limit,
            organization_id=organization_id,
            search=search,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
        )
        return [meeting_to_dict(m) for m in meetings]

    async def count_meetings(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> int:
        return await self.repository.count(
            db,
            organization_id=organization_id,
            search=search,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
        )

    async def get_meeting(self, db: AsyncSession, meeting_id: str, organization_id: str) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        attendees = await self.repository.list_attendee_emails(db, meeting_id)
        return meeting_to_dict(meeting, attendees)

    async def schedule_meeting(
        self, db: AsyncSession, payload: MeetingCreate, current_user: User | None = None
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        start_time = parse_datetime(payload.start_time)
        end_time = parse_datetime(payload.end_time)
        if end_time <= start_time:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_MEETING_RANGE",
                message="Meeting end time must be after its start time",
            )
        from app.services.crm_relationship_service import validate_crm_relationships

        relationships = await validate_crm_relationships(
            db,
            organization_id=org_id,
            lead_id=payload.lead_id,
            contact_id=payload.contact_id,
            company_id=payload.company_id,
            deal_id=payload.deal_id,
        )
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "start_time": start_time,
            "end_time": end_time,
            "meeting_link": payload.meeting_link,
            "location": payload.location,
            **relationships,
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

    async def get_upcoming_meetings(self, db: AsyncSession, organization_id: str) -> list[dict]:
        meetings = await self.repository.list_upcoming(db, organization_id=organization_id)
        return [meeting_to_dict(m) for m in meetings]

    async def bulk_cancel(self, db: AsyncSession, ids: list[str], organization_id: str) -> dict:
        meetings = await self.repository.list_by_ids(db, ids=ids, organization_id=organization_id)
        for meeting in meetings:
            meeting.status = "Cancelled"
        await self._commit(db, "Failed to cancel meetings")
        return {"affected_count": len(meetings), "message": "Meetings cancelled successfully"}

    async def update_meeting(
        self,
        db: AsyncSession,
        meeting_id: str,
        payload: MeetingUpdate,
        organization_id: str,
    ) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("title"):
            meeting.title = updates["title"]
        if updates.get("start_time"):
            meeting.start_time = parse_datetime(updates["start_time"])
        if updates.get("end_time"):
            meeting.end_time = parse_datetime(updates["end_time"])
        if meeting.end_time <= meeting.start_time:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_MEETING_RANGE",
                message="Meeting end time must be after its start time",
            )
        if "meeting_link" in updates:
            meeting.meeting_link = updates["meeting_link"]
        if "location" in updates:
            meeting.location = updates["location"]
        relationship_fields = {"lead_id", "contact_id", "company_id", "deal_id"}
        if relationship_fields & updates.keys():
            from app.services.crm_relationship_service import validate_crm_relationships

            merged = {
                field: updates.get(field, getattr(meeting, field)) for field in relationship_fields
            }
            relationships = await validate_crm_relationships(
                db, organization_id=organization_id, **merged
            )
            for field in relationship_fields & updates.keys():
                setattr(meeting, field, relationships[field])
        await self._commit(db, "Failed to update meeting")
        await db.refresh(meeting)
        attendees = await self.repository.list_attendee_emails(db, meeting_id)
        return meeting_to_dict(meeting, attendees)

    async def cancel_meeting(self, db: AsyncSession, meeting_id: str, organization_id: str) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        meeting.status = "Cancelled"
        await self._commit(db, "Failed to cancel meeting")
        return {"message": f"Meeting {meeting_id} cancelled", "status": "success"}

    async def complete_meeting(
        self, db: AsyncSession, meeting_id: str, organization_id: str
    ) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        if meeting.status != "Scheduled":
            raise APIException(
                message="Only scheduled meetings can be completed",
                code="INVALID_MEETING_STATUS",
                status_code=409,
            )
        meeting.status = "Completed"
        await self._commit(db, "Failed to complete meeting")
        return {"message": f"Meeting {meeting_id} completed", "status": "success"}

    async def reschedule_meeting(
        self,
        db: AsyncSession,
        meeting_id: str,
        new_start_time: str,
        new_end_time: str,
        organization_id: str,
    ) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        start_time = parse_datetime(new_start_time)
        end_time = parse_datetime(new_end_time)
        if end_time <= start_time:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_MEETING_RANGE",
                message="Meeting end time must be after its start time",
            )
        meeting.start_time = start_time
        meeting.end_time = end_time
        await self._commit(db, "Failed to reschedule meeting")
        return {
            "message": f"Meeting {meeting_id} rescheduled to {new_start_time}",
            "status": "success",
        }

    async def rsvp(
        self,
        db: AsyncSession,
        meeting_id: str,
        email: str,
        response: str,
        organization_id: str,
    ) -> dict:
        meeting = await self.repository.get_by_id(
            db, meeting_id=meeting_id, organization_id=organization_id
        )
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
        meeting = await self.repository.get_by_id(
            db,
            meeting_id=meeting_id,
            organization_id=current_user.organization_id or "",
        )
        if not meeting:
            raise NotFoundError(message=f"Meeting '{meeting_id}' not found")
        await self.ai_service.analyze_meeting(db, meeting_id, transcript_text, current_user)
        return {"message": f"Transcript uploaded for meeting {meeting_id}", "status": "success"}

    async def get_ai_summary(self, db: AsyncSession, meeting_id: str, current_user: User) -> dict:
        meeting = await self.repository.get_by_id(
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
        meeting = await self.repository.get_by_id(
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
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="Zoom integration is not configured",
        )

    async def create_teams_link(self, subject: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="Microsoft Teams integration is not configured",
        )

    async def export_ical(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message="iCal export is not available",
        )


meeting_service = MeetingService()
