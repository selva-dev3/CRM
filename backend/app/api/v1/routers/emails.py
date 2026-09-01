from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    EmailResponse,
    EmailSendRequest,
    MessageResponse,
)
from app.services.email_domain_service import email_domain_service

router = APIRouter()


@router.get(
    "/inbox",
    summary="Fetch unified inbox email messages",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def get_inbox(
    page: int = 1,
    limit: int = 20,
    folder: str = "inbox",
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await email_domain_service.get_inbox(db, page=page, limit=limit, search=search)


@router.post(
    "/send",
    response_model=EmailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send single outbound email",
    dependencies=[Depends(require_permission("emails:send"))],
)
async def send_email(payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.send_email(db, payload)


@router.get(
    "/drafts",
    summary="List saved email drafts",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def list_drafts(db: AsyncSession = Depends(get_db)):
    return await email_domain_service.list_drafts()


@router.post(
    "/drafts",
    response_model=MessageResponse,
    summary="Save draft email message",
    dependencies=[Depends(require_permission("emails:send"))],
)
async def save_draft(payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.save_draft()


@router.get(
    "/drafts/{draft_id}",
    summary="Get draft email by ID",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def get_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.get_draft(draft_id)


@router.delete(
    "/drafts/{draft_id}",
    response_model=MessageResponse,
    summary="Delete draft email",
    dependencies=[Depends(require_permission("emails:delete"))],
)
async def delete_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.delete_draft(draft_id)


@router.get(
    "/templates",
    summary="List email templates",
    dependencies=[Depends(require_permission("emails:templates"))],
)
async def list_email_templates(db: AsyncSession = Depends(get_db)):
    return await email_domain_service.list_templates(db)


@router.post(
    "/templates",
    response_model=MessageResponse,
    summary="Create new email template",
    dependencies=[Depends(require_permission("emails:templates"))],
)
async def create_email_template(
    name: str,
    subject: str,
    body: str,
    category: str = "General",
    db: AsyncSession = Depends(get_db),
):
    return await email_domain_service.create_template(
        db, name=name, subject=subject, body=body, category=category
    )


@router.get(
    "/templates/{template_id}",
    summary="Get email template by ID",
    dependencies=[Depends(require_permission("emails:templates"))],
)
async def get_email_template(template_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.get_template(db, template_id)


@router.put(
    "/templates/{template_id}",
    response_model=MessageResponse,
    summary="Update email template",
    dependencies=[Depends(require_permission("emails:templates"))],
)
async def update_email_template(
    template_id: str,
    name: str,
    subject: str,
    body: str,
    db: AsyncSession = Depends(get_db),
):
    return await email_domain_service.update_template(
        db, template_id=template_id, name=name, subject=subject, body=body
    )


@router.delete(
    "/templates/{template_id}",
    response_model=MessageResponse,
    summary="Delete email template",
    dependencies=[Depends(require_permission("emails:templates"))],
)
async def delete_email_template(template_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.delete_template(db, template_id)


@router.post(
    "/campaigns/send-bulk",
    summary="Send bulk email campaign blast to target list",
    dependencies=[Depends(require_permission("emails:send"))],
)
async def send_bulk_campaign(
    template_id: str, lead_ids: list[str], db: AsyncSession = Depends(get_db)
):
    return await email_domain_service.send_bulk_campaign(template_id, lead_ids)


@router.get(
    "/tracking/{email_id}/status",
    summary="Get email open & link click analytics",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def get_email_tracking(email_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.get_email_tracking(email_id)


@router.get(
    "/signatures",
    summary="List user email signatures",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def get_email_signatures(db: AsyncSession = Depends(get_db)):
    return await email_domain_service.get_email_signatures()


@router.post(
    "/signatures",
    response_model=MessageResponse,
    summary="Create or update user email signature",
    dependencies=[Depends(require_permission("emails:send"))],
)
async def save_email_signature(name: str, html: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.save_email_signature(name, html)


@router.get(
    "/threads/{thread_id}",
    summary="Get full email conversation thread",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def get_email_thread(thread_id: str, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.get_email_thread(thread_id)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete emails from inbox",
    dependencies=[Depends(require_permission("emails:delete"))],
)
async def bulk_delete_emails(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await email_domain_service.bulk_delete(db, payload.ids)


@router.post(
    "/sync/imap",
    response_model=MessageResponse,
    summary="Trigger IMAP/SMTP background mail sync",
    dependencies=[Depends(require_permission("emails:read"))],
)
async def sync_imap_inbox(db: AsyncSession = Depends(get_db)):
    return await email_domain_service.sync_imap_inbox()
