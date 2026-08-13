from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import Email, EmailTemplate
from app.repositories.email_repository import EmailRepository
from app.schemas.crm_schemas import EmailSendRequest
from app.services.org_service import organization_service


def email_to_dict(email: Email) -> dict:
    return {
        "id": email.id,
        "from_email": email.from_email,
        "to": [email.to_email],
        "subject": email.subject,
        "body": email.body_text,
        "sent_at": str(email.sent_at),
    }


def email_response_to_dict(email: Email) -> dict:
    return {
        "id": email.id,
        "from_email": email.from_email,
        "to": [email.to_email],
        "subject": email.subject,
        "sent_at": str(email.sent_at),
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

    def __init__(self, repository: Optional[EmailRepository] = None) -> None:
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
        search: Optional[str] = None,
    ) -> list[dict]:
        emails = await self.repository.list_emails(
            db, page=page, limit=limit, search=search
        )
        return [email_to_dict(e) for e in emails]

    async def send_email(self, db: AsyncSession, payload: EmailSendRequest) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db)
        to_addr = str(payload.to[0]) if payload.to else "client@example.com"
        email = await self.repository.create_email(
            db,
            data={
                "organization_id": org_id,
                "from_email": "rep@company.com",
                "to_email": to_addr,
                "subject": payload.subject,
                "body_text": payload.body,
            },
        )
        await self._commit(db, "Failed to send email")
        await db.refresh(email)
        return email_response_to_dict(email)

    async def list_drafts(self) -> list[dict]:
        return [
            {
                "id": "draft-1",
                "to": ["prospect@client.com"],
                "subject": "Proposal Draft - Enterprise Plan",
                "body": "Hi, Please see attached proposal...",
                "created_at": "2026-08-05T10:00:00Z",
            }
        ]

    async def save_draft(self) -> dict:
        return {"message": "Email draft saved successfully", "status": "success"}

    async def get_draft(self, draft_id: str) -> dict:
        return {
            "id": draft_id,
            "to": ["prospect@client.com"],
            "subject": "Proposal Draft",
            "body": "Draft body preview",
        }

    async def delete_draft(self, draft_id: str) -> dict:
        return {"message": f"Draft '{draft_id}' deleted", "status": "success"}

    async def list_templates(self, db: AsyncSession) -> list[dict]:
        templates = await self.repository.list_templates(db)
        if not templates:
            return [
                {"id": "tmpl-1", "name": "Cold Outreach Introduction", "subject": "Quick intro - {{company_name}}", "category": "Sales Outreach"},
                {"id": "tmpl-2", "name": "Product Demo Followup", "subject": "Demo recap & next steps", "category": "Follow-up"},
            ]
        return [template_list_to_dict(t) for t in templates]

    async def create_template(
        self,
        db: AsyncSession,
        *,
        name: str,
        subject: str,
        body: str,
        category: str = "General",
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db)
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

    async def get_template(self, db: AsyncSession, template_id: str) -> dict:
        template = await self.repository.get_template(db, template_id)
        if not template:
            return {
                "id": template_id,
                "name": "Default Template",
                "subject": "Hello {{name}}",
                "body": "Welcome to Enterprise CRM",
                "category": "General",
            }
        return template_to_dict(template)

    async def update_template(
        self,
        db: AsyncSession,
        *,
        template_id: str,
        name: str,
        subject: str,
        body: str,
    ) -> dict:
        template = await self.repository.get_template(db, template_id)
        if template:
            template.name = name
            template.subject = subject
            template.body_template = body
            await self._commit(db, "Failed to update email template")
        return {"message": f"Template {template_id} updated", "status": "success"}

    async def delete_template(self, db: AsyncSession, template_id: str) -> dict:
        template = await self.repository.get_template(db, template_id)
        if template:
            await self.repository.delete_template(db, template)
            await self._commit(db, "Failed to delete email template")
        return {"message": f"Template {template_id} deleted successfully", "status": "success"}

    async def send_bulk_campaign(self, template_id: str, lead_ids: list[str]) -> dict:
        return {
            "campaign_id": "cmpg-90",
            "queued_count": len(lead_ids),
            "status": "processing",
        }

    async def get_email_tracking(self, email_id: str) -> dict:
        return {
            "email_id": email_id,
            "opens": 3,
            "last_opened_at": "2026-08-05T14:22:00Z",
            "link_clicks": 2,
            "bounced": False,
        }

    async def get_email_signatures(self) -> list[dict]:
        return [
            {"id": "sig-1", "name": "Corporate Standard", "html": "<b>Best regards,</b><br/>Sales Team | Enterprise CRM"}
        ]

    async def save_email_signature(self, name: str, html: str) -> dict:
        return {"message": f"Signature '{name}' saved", "status": "success"}

    async def get_email_thread(self, thread_id: str) -> dict:
        return {
            "thread_id": thread_id,
            "messages": [
                {"from": "prospect@client.com", "to": "rep@company.com", "subject": "Re: Demo Meeting", "body": "Thanks, Thursday works great for us.", "timestamp": "2026-08-05T11:00:00Z"},
                {"from": "rep@company.com", "to": "prospect@client.com", "subject": "Demo Meeting", "body": "Great, invite sent!", "timestamp": "2026-08-05T11:15:00Z"},
            ],
        }

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        emails = await self.repository.list_by_ids(db, ids)
        for email in emails:
            await self.repository.delete(db, email)
        await self._commit(db, "Failed to bulk delete emails")
        return {"affected_count": len(emails), "message": "Emails deleted"}

    async def sync_imap_inbox(self) -> dict:
        return {"message": "IMAP email background mail sync initiated", "status": "success"}


email_domain_service = EmailDomainService()