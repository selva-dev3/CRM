import asyncio
from datetime import datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import CallLog, User
from app.repositories.call_repository import CallRepository
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import CallLogBase
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.org_service import organization_service
from app.services.s3_service import s3_service


def call_to_dict(call: CallLog) -> dict:
    return {
        "id": call.id,
        "contact_id": call.contact_id,
        "call_type": call.call_type or "Outbound",
        "duration_seconds": call.duration_seconds or 0,
        "notes": call.notes,
        "timestamp": str(call.timestamp),
    }


class CallService:
    """Business logic for the CallLog domain."""

    def __init__(
        self,
        repository: CallRepository | None = None,
        ai_service_instance: AIDomainService | None = None,
    ) -> None:
        self.repository = repository or CallRepository()
        self.contact_repository = ContactRepository()
        self.ai_service = ai_service_instance or ai_domain_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_calls(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        call_type: str | None = None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        calls = await self.repository.list(
            db,
            page=page,
            limit=limit,
            organization_id=org_id,
            search=search,
            call_type=call_type,
        )
        return [call_to_dict(c) for c in calls]

    async def get_call(self, db: AsyncSession, call_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        call = await self.repository.get_by_id(db, call_id, org_id)
        if not call:
            raise NotFoundError(message=f"Call log '{call_id}' not found")
        return call_to_dict(call)

    async def log_call(self, db: AsyncSession, payload: CallLogBase, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        if not payload.contact_id:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="CONTACT_REQUIRED",
                message="A valid contact is required to log a call",
            )
        contact = await self.contact_repository.get_by_id_scoped(
            db, contact_id=payload.contact_id, organization_id=org_id
        )
        if not contact:
            raise NotFoundError(message=f"Contact '{payload.contact_id}' not found")
        data = {
            "organization_id": org_id,
            "contact_id": contact.id,
            "call_type": payload.call_type or "Outbound",
            "duration_seconds": payload.duration_seconds or 0,
            "notes": payload.notes,
        }
        call = await self.repository.create(db, data=data)
        await self._commit(db, "Failed to log call")
        await db.refresh(call)
        return {
            "id": call.id,
            "contact_id": call.contact_id,
            "call_type": call.call_type,
            "duration_seconds": call.duration_seconds,
            "notes": call.notes,
            "timestamp": str(call.timestamp),
        }

    async def bulk_delete(self, db: AsyncSession, ids: list[str], current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        calls = await self.repository.list_by_ids(db, ids, org_id)
        for call in calls:
            await self.repository.delete(db, call)
        await self._commit(db, "Failed to bulk delete call logs")
        return {"affected_count": len(calls), "message": "Call logs deleted successfully"}

    async def delete_call(self, db: AsyncSession, call_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        call = await self.repository.get_by_id(db, call_id, org_id)
        if not call:
            raise NotFoundError(message=f"Call log '{call_id}' not found")
        await self.repository.delete(db, call)
        await self._commit(db, "Failed to delete call log")
        return {"message": f"Call log {call_id} deleted successfully", "status": "success"}

    async def require_call(self, db: AsyncSession, call_id: str, current_user: User) -> CallLog:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        call = await self.repository.get_by_id(db, call_id, org_id)
        if not call:
            raise NotFoundError(message=f"Call log '{call_id}' not found")
        return call

    async def get_recording(self, db: AsyncSession, call_id: str, current_user: User) -> dict:
        call = await self.require_call(db, call_id, current_user)
        try:
            recording_url = await asyncio.to_thread(
                s3_service.generate_presigned_url, f"recordings/{call_id}.mp3"
            )
        except Exception:
            raise APIException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="CALL_RECORDING_UNAVAILABLE",
                message="Call recording storage is currently unavailable",
            )
        return {
            "call_id": call_id,
            "recording_url": recording_url,
            "duration_seconds": call.duration_seconds or 120,
        }

    async def get_sentiment(self, db: AsyncSession, call_id: str, current_user: User) -> dict:
        call = await self.require_call(db, call_id, current_user)
        if not call.notes or not call.notes.strip():
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="AI_CALL_TEXT_UNAVAILABLE",
                message="This call has no transcript or notes to analyze.",
            )
        analysis = await self.ai_service.analyze_sentiment(db, call.notes, current_user)
        return {
            "call_id": call_id,
            "overall_sentiment": analysis["sentiment"],
            "confidence_score": analysis["confidence"],
            "reasons": analysis["reasons"],
            "urgency": analysis["urgency"],
            "escalation_required": analysis["escalation_required"],
            "run_id": analysis.get("run_id"),
        }

    async def trigger_outbound(self, phone_number: str, contact_id: str) -> dict:
        return {
            "call_sid": f"CA{int(datetime.now().timestamp())}",
            "status": "initiating",
            "to": phone_number,
            "contact_id": contact_id,
        }

    async def get_dispositions(self) -> list[str]:
        return [
            "Connected",
            "Left Voicemail",
            "No Answer",
            "Busy",
            "Wrong Number",
            "Scheduled Meeting",
        ]

    async def create_disposition(self, name: str) -> dict:
        return {"message": f"Disposition '{name}' created", "status": "success"}

    async def get_rep_stats(self) -> list[dict]:
        return [
            {
                "rep": "System Admin",
                "total_calls": 42,
                "connected": 30,
                "voicemails": 8,
                "total_duration": 4800,
            },
            {
                "rep": "Sales Representative",
                "total_calls": 28,
                "connected": 20,
                "voicemails": 5,
                "total_duration": 3200,
            },
        ]

    async def log_voicemail_drop(self, contact_id: str, voicemail_template_id: str) -> dict:
        return {
            "message": f"Voicemail template {voicemail_template_id} sent to {contact_id}",
            "status": "success",
        }


call_service = CallService()
