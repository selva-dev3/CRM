import asyncio
import hashlib
import json
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import get_logger
from app.models import Email, EmailTemplate, User
from app.repositories.email_repository import EmailRepository
from app.schemas.crm_schemas import EmailSendRequest
from app.services.email_service import EmailDeliveryUnknownError, send_tracked_email
from app.services.org_service import organization_service

logger = get_logger(__name__)


def email_to_dict(email: Email) -> dict:
    return {
        "id": email.id,
        "from_email": email.from_email,
        "to": [email.to_email],
        "subject": email.subject,
        "body": email.body_text,
        "status": email.status,
        "sent_at": email.sent_at.isoformat() if email.sent_at else None,
        "provider_message_id": email.provider_message_id,
        "failure_reason": email.failure_reason,
        "created_at": email.created_at.isoformat() if email.created_at else None,
        "lead_id": email.lead_id,
        "contact_id": email.contact_id,
        "company_id": email.company_id,
        "deal_id": email.deal_id,
    }


def email_response_to_dict(email: Email) -> dict:
    return {
        "id": email.id,
        "from_email": email.from_email,
        "to": [email.to_email],
        "subject": email.subject,
        "body": email.body_text,
        "status": email.status,
        "sent_at": email.sent_at.isoformat() if email.sent_at else None,
        "provider_message_id": email.provider_message_id,
        "failure_reason": email.failure_reason,
        "created_at": email.created_at.isoformat() if email.created_at else None,
        "lead_id": email.lead_id,
        "contact_id": email.contact_id,
        "company_id": email.company_id,
        "deal_id": email.deal_id,
    }


def template_to_dict(template: EmailTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "body": template.body_template,
        "category": template.category,
    }


def template_list_to_dict(template: EmailTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "category": template.category,
    }


class EmailDomainService:
    """Business logic for the Email / EmailTemplate domains."""

    def __init__(self, repository: EmailRepository | None = None) -> None:
        self.repository = repository or EmailRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def get_inbox(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        emails = await self.repository.list_emails(
            db, page=page, limit=limit, organization_id=org_id, search=search
        )
        return [email_to_dict(e) for e in emails]

    async def count_inbox(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        current_user: User,
    ) -> int:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.repository.count_emails(db, organization_id=org_id, search=search)

    async def send_email(
        self,
        db: AsyncSession,
        payload: EmailSendRequest,
        current_user: User,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.queue_email(
            db,
            organization_id=org_id,
            to_email=str(payload.to[0]) if payload.to else "",
            subject=payload.subject,
            body=payload.body,
            idempotency_key=idempotency_key,
            lead_id=payload.lead_id,
            contact_id=payload.contact_id,
            company_id=payload.company_id,
            deal_id=payload.deal_id,
        )

    async def queue_email(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        to_email: str,
        subject: str,
        body: str,
        idempotency_key: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> dict:
        """Persist a truthful pending delivery; the worker owns provider I/O."""
        if not settings.BREVO_API_KEY:
            raise APIException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="EMAIL_PROVIDER_NOT_CONFIGURED",
                message="Email delivery provider is not configured",
            )
        to_addr = to_email.strip()
        if not to_addr:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="EMAIL_RECIPIENT_REQUIRED",
                message="At least one email recipient is required",
            )
        from app.services.crm_relationship_service import validate_crm_relationships

        relationships = await validate_crm_relationships(
            db,
            organization_id=organization_id,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
        )
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "to": to_addr.casefold(),
                    "subject": subject,
                    "body": body,
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "company_id": company_id,
                    "deal_id": deal_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if idempotency_key:
            existing = await self.repository.get_by_idempotency_key(
                db,
                organization_id=organization_id,
                idempotency_key=idempotency_key,
            )
            if existing:
                if existing.request_hash != request_hash:
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="EMAIL_IDEMPOTENCY_CONFLICT",
                        message="This idempotency key was already used for another email",
                    )
                return email_response_to_dict(existing)
        email = await self.repository.create_email(
            db,
            data={
                "organization_id": organization_id,
                **relationships,
                "from_email": settings.EMAILS_FROM_EMAIL,
                "to_email": to_addr,
                "subject": subject,
                "body_text": body,
                "status": "Pending",
                "idempotency_key": idempotency_key,
                "request_hash": request_hash,
            },
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if idempotency_key:
                existing = await self.repository.get_by_idempotency_key(
                    db,
                    organization_id=organization_id,
                    idempotency_key=idempotency_key,
                )
                if existing and existing.request_hash == request_hash:
                    return email_response_to_dict(existing)
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="EMAIL_IDEMPOTENCY_CONFLICT",
                message="The email request conflicts with an existing delivery",
            ) from exc
        except Exception:
            await db.rollback()
            raise
        await db.refresh(email)
        return email_response_to_dict(email)

    async def list_drafts(self, db: AsyncSession, current_user: User) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        drafts = await self.repository.list_drafts(db, organization_id=org_id)
        return [email_response_to_dict(draft) for draft in drafts]

    async def save_draft(
        self, db: AsyncSession, payload: EmailSendRequest, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        draft = await self.repository.create_email(
            db,
            data={
                "organization_id": org_id,
                "from_email": settings.EMAILS_FROM_EMAIL,
                "to_email": str(payload.to[0]),
                "subject": payload.subject,
                "body_text": payload.body,
                "status": "Draft",
            },
        )
        await self._commit(db, "Failed to save email draft")
        await db.refresh(draft)
        return email_response_to_dict(draft)

    async def get_draft(self, db: AsyncSession, draft_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        draft = await self.repository.get_email(db, email_id=draft_id, organization_id=org_id)
        if not draft or draft.status != "Draft":
            raise APIException(message="Email draft not found", status_code=404)
        return email_response_to_dict(draft)

    async def delete_draft(self, db: AsyncSession, draft_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        draft = await self.repository.get_email(db, email_id=draft_id, organization_id=org_id)
        if not draft or draft.status != "Draft":
            raise APIException(message="Email draft not found", status_code=404)
        await self.repository.delete(db, draft)
        await self._commit(db, "Failed to delete email draft")
        return {"message": "Email draft deleted", "status": "success"}

    async def list_templates(self, db: AsyncSession, current_user: User) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        templates = await self.repository.list_templates(db, org_id)
        return [template_list_to_dict(t) for t in templates]

    async def create_template(
        self,
        db: AsyncSession,
        *,
        name: str,
        subject: str,
        body: str,
        category: str = "General",
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        await self.repository.create_template(
            db,
            data={
                "organization_id": org_id,
                "name": name,
                "subject": subject,
                "body_template": body,
                "category": category,
            },
        )
        await self._commit(db, "Failed to create email template")
        return {"message": f"Template '{name}' created", "status": "success"}

    async def get_template(self, db: AsyncSession, template_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        template = await self.repository.get_template(db, template_id, org_id)
        if not template:
            raise APIException(message="Email template not found", status_code=404)
        return template_to_dict(template)

    async def update_template(
        self,
        db: AsyncSession,
        *,
        template_id: str,
        name: str,
        subject: str,
        body: str,
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        template = await self.repository.get_template(db, template_id, org_id)
        if not template:
            raise APIException(message="Email template not found", status_code=404)
        template.name = name
        template.subject = subject
        template.body_template = body
        await self._commit(db, "Failed to update email template")
        return {"message": f"Template {template_id} updated", "status": "success"}

    async def delete_template(self, db: AsyncSession, template_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        template = await self.repository.get_template(db, template_id, org_id)
        if not template:
            raise APIException(message="Email template not found", status_code=404)
        await self.repository.delete_template(db, template)
        await self._commit(db, "Failed to delete email template")
        return {"message": f"Template {template_id} deleted successfully", "status": "success"}

    async def send_bulk_campaign(self, template_id: str, lead_ids: list[str]) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="EMAIL_CAMPAIGNS_NOT_SUPPORTED",
            message="Email campaigns are not configured",
        )

    async def get_email_tracking(self, email_id: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="EMAIL_TRACKING_NOT_SUPPORTED",
            message="Email tracking is not configured",
        )

    async def get_email_signatures(self) -> list[dict]:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="EMAIL_SIGNATURES_NOT_SUPPORTED",
            message="Email signatures are not configured",
        )

    async def save_email_signature(self, name: str, html: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="EMAIL_SIGNATURES_NOT_SUPPORTED",
            message="Email signatures are not configured",
        )

    async def get_email_thread(self, thread_id: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="EMAIL_THREADS_NOT_SUPPORTED",
            message="Inbound email threads are not configured",
        )

    async def bulk_delete(self, db: AsyncSession, ids: list[str], current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        emails = await self.repository.list_by_ids(db, ids, org_id)
        for email in emails:
            await self.repository.delete(db, email)
        await self._commit(db, "Failed to bulk delete emails")
        return {"affected_count": len(emails), "message": "Emails deleted"}

    async def sync_imap_inbox(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="IMAP_NOT_CONFIGURED",
            message="IMAP synchronization is not configured",
        )

    async def retry_email(self, db: AsyncSession, email_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        email = await self.repository.retry_failed(db, email_id=email_id, organization_id=org_id)
        if not email:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="EMAIL_NOT_RETRYABLE",
                message="Only a failed email can be retried",
            )
        await self._commit(db, "Failed to retry email")
        await db.refresh(email)
        return email_response_to_dict(email)

    async def deliver_one(self, session_factory) -> bool:
        async with session_factory() as db:
            now = datetime.now(UTC)
            await self.repository.expire_delivery_claims(db, now)
            email = await self.repository.claim_delivery(db, now)
            if not email:
                await db.commit()
                return False
            email_id = email.id
            org_id = email.organization_id
            recipient = email.to_email
            subject = email.subject
            body = email.body_html or email.body_text or ""
            await db.commit()

        provider_message_id = None
        delivery_status = "Failed"
        failure_reason = None
        try:
            provider_message_id = await asyncio.to_thread(
                send_tracked_email,
                to_email=recipient,
                subject=subject,
                html_content=body,
                idempotency_key=email_id,
            )
            delivery_status = "Sent"
        except EmailDeliveryUnknownError:
            delivery_status = "Unknown"
            failure_reason = "Provider delivery outcome could not be confirmed"
        except ValueError:
            delivery_status = "Failed"
            failure_reason = "Provider rejected the delivery request"
        except Exception as exc:
            delivery_status = "Unknown"
            failure_reason = "Unexpected provider delivery failure"
            logger.warning(
                "Email delivery failed organization_id=%s email_id=%s error_type=%s",
                org_id,
                email_id,
                type(exc).__name__,
            )

        async with session_factory() as db:
            email = await self.repository.get_email(db, email_id=email_id, organization_id=org_id)
            if email and email.status == "Processing":
                await self.repository.record_delivery_result(
                    db,
                    email,
                    status=delivery_status,
                    provider_message_id=provider_message_id,
                    failure_reason=failure_reason,
                )
                await db.commit()
        return True


email_domain_service = EmailDomainService()
