import asyncio
import hashlib
import json

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import CallLog, User
from app.repositories.call_repository import CallRepository
from app.schemas.crm_schemas import CallLogBase, CallLogUpdate
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.org_service import organization_service
from app.services.s3_service import s3_service


def call_to_dict(call: CallLog) -> dict:
    creator = getattr(call, "created_by_user", None)
    return {
        "id": call.id,
        "contact_id": call.contact_id,
        "lead_id": call.lead_id,
        "company_id": call.company_id,
        "deal_id": call.deal_id,
        "call_type": call.call_type or "Outbound",
        "disposition": call.disposition,
        "duration_seconds": call.duration_seconds or 0,
        "subject": call.subject,
        "notes": call.notes,
        "follow_up_required": call.follow_up_required,
        "follow_up_at": str(call.follow_up_at) if call.follow_up_at else None,
        "next_action": call.next_action,
        "created_by": call.created_by,
        "created_by_name": getattr(creator, "name", None),
        "timestamp": str(call.timestamp),
        "created_at": str(call.created_at or call.timestamp),
        "updated_at": str(call.updated_at or call.created_at or call.timestamp),
    }


def _normalized_text(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _request_hash(payload: CallLogBase) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json", exclude_none=False),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CallService:
    """Business logic for the CallLog domain."""

    def __init__(
        self,
        repository: CallRepository | None = None,
        ai_service_instance: AIDomainService | None = None,
    ) -> None:
        self.repository = repository or CallRepository()
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
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
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
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
        )
        return [call_to_dict(c) for c in calls]

    async def count_calls(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        call_type: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        current_user: User,
    ) -> int:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.repository.count(
            db,
            organization_id=org_id,
            search=search,
            call_type=call_type,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
        )

    async def get_call(self, db: AsyncSession, call_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        call = await self.repository.get_by_id(db, call_id, org_id)
        if not call:
            raise NotFoundError(message=f"Call log '{call_id}' not found")
        return call_to_dict(call)

    async def log_call(
        self,
        db: AsyncSession,
        payload: CallLogBase,
        current_user: User,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        if not any((payload.contact_id, payload.lead_id, payload.company_id, payload.deal_id)):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="CONTACT_REQUIRED",
                message="A related lead, contact, company, or deal is required to log a call",
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
        request_hash = _request_hash(payload)
        if idempotency_key:
            existing = await self.repository.get_by_idempotency_key(
                db,
                organization_id=org_id,
                created_by=current_user.id,
                idempotency_key=idempotency_key,
            )
            if existing:
                if existing.idempotency_request_hash != request_hash:
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="IDEMPOTENCY_KEY_REUSED",
                        message="Idempotency-Key was already used with different call data",
                    )
                return call_to_dict(existing)
        data = {
            "organization_id": org_id,
            **relationships,
            "call_type": payload.call_type,
            "disposition": payload.disposition,
            "duration_seconds": payload.duration_seconds,
            "subject": _normalized_text(payload.subject),
            "notes": _normalized_text(payload.notes),
            "follow_up_required": payload.follow_up_required,
            "follow_up_at": payload.follow_up_at if payload.follow_up_required else None,
            "next_action": _normalized_text(payload.next_action),
            "created_by": current_user.id,
            "idempotency_key": idempotency_key,
            "idempotency_request_hash": request_hash if idempotency_key else None,
        }
        if payload.timestamp is not None:
            data["timestamp"] = payload.timestamp
        call = await self.repository.create(db, data=data)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if idempotency_key:
                existing = await self.repository.get_by_idempotency_key(
                    db,
                    organization_id=org_id,
                    created_by=current_user.id,
                    idempotency_key=idempotency_key,
                )
                if existing and existing.idempotency_request_hash == request_hash:
                    return call_to_dict(existing)
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="CALL_LOG_CONFLICT",
                message="The call could not be logged because it conflicts with existing data",
            ) from exc
        except Exception as exc:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to log call",
            ) from exc
        await db.refresh(call)
        return call_to_dict(call)

    async def update_call(
        self,
        db: AsyncSession,
        call_id: str,
        payload: CallLogUpdate,
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        call = await self.repository.get_by_id(db, call_id, org_id)
        if not call:
            raise NotFoundError(message=f"Call log '{call_id}' not found")

        fields = payload.model_fields_set
        relationship_values = {
            "lead_id": call.lead_id,
            "contact_id": payload.contact_id if "contact_id" in fields else call.contact_id,
            "company_id": payload.company_id if "company_id" in fields else call.company_id,
            "deal_id": payload.deal_id if "deal_id" in fields else call.deal_id,
        }
        if not any(relationship_values.values()):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="CONTACT_REQUIRED",
                message="A related lead, contact, company, or deal is required to log a call",
            )
        from app.services.crm_relationship_service import validate_crm_relationships

        relationships = await validate_crm_relationships(
            db, organization_id=org_id, **relationship_values
        )
        data = payload.model_dump(exclude_unset=True)
        for name in ("subject", "notes", "next_action"):
            if name in data:
                data[name] = _normalized_text(data[name])
        for name in ("contact_id", "company_id", "deal_id"):
            if name in data:
                data[name] = relationships[name]

        follow_up_required = data.get("follow_up_required", call.follow_up_required)
        follow_up_at = data.get("follow_up_at", call.follow_up_at)
        if follow_up_required and follow_up_at is None:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="FOLLOW_UP_DATE_REQUIRED",
                message="A follow-up date is required when follow-up is enabled",
            )
        if not follow_up_required:
            data["follow_up_at"] = None

        await self.repository.update(db, call, data=data)
        await self._commit(db, "Failed to update call log")
        await db.refresh(call)
        return call_to_dict(call)

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
        if not call.recording_url:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CALL_RECORDING_NOT_FOUND",
                message="This call log has no recording",
            )
        try:
            recording_url = await asyncio.to_thread(
                s3_service.generate_presigned_url, call.recording_url
            )
        except Exception as exc:
            raise APIException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="CALL_RECORDING_UNAVAILABLE",
                message="Call recording storage is currently unavailable",
            ) from exc
        return {
            "call_id": call_id,
            "recording_url": recording_url,
            "duration_seconds": call.duration_seconds or 0,
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
        raise APIException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="CALL_PROVIDER_NOT_CONFIGURED",
            message="Outbound calling is unavailable because no telephony provider is configured",
        )

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
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="CUSTOM_CALL_DISPOSITIONS_NOT_SUPPORTED",
            message="Custom call dispositions are not supported",
        )

    async def get_rep_stats(self) -> list[dict]:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="CALL_REP_STATS_NOT_SUPPORTED",
            message="Call performance reporting requires provider call ownership data",
        )

    async def log_voicemail_drop(self, contact_id: str, voicemail_template_id: str) -> dict:
        raise APIException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="VOICEMAIL_PROVIDER_NOT_CONFIGURED",
            message="Voicemail delivery is unavailable because no telephony provider is configured",
        )


call_service = CallService()
