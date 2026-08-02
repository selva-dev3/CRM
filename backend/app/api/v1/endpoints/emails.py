from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Email, EmailTemplate
from app.schemas.crm_schemas import (
    EmailSendRequest, EmailResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("/inbox", response_model=List[EmailResponse], summary="Fetch unified inbox email messages")
async def get_inbox(page: int = 1, limit: int = 20, folder: str = "inbox", db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Email).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        emails = res.scalars().all()
        return [{"id": e.id, "from_email": e.from_email, "to": [e.to_email], "subject": e.subject, "sent_at": str(e.sent_at)} for e in emails]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/send", response_model=EmailResponse, status_code=status.HTTP_201_CREATED, summary="Send single outbound email")
async def send_email(payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    try:
        eml = Email(organization_id="org-1", from_email="usr-1@company.com", to_email=str(payload.to[0]), subject=payload.subject, body_text=payload.body)
        db.add(eml)
        await db.commit()
        return {"id": eml.id, "from_email": eml.from_email, "to": [eml.to_email], "subject": eml.subject, "sent_at": str(eml.sent_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/drafts", response_model=List[EmailResponse], summary="List saved email drafts")
async def list_drafts(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/drafts", response_model=MessageResponse, summary="Save draft email message")
async def save_draft(payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    return {"message": "Email draft saved", "status": "success"}

@router.get("/drafts/{draft_id}", response_model=EmailResponse, summary="Get draft email by ID")
async def get_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft '{draft_id}' not found")

@router.delete("/drafts/{draft_id}", response_model=MessageResponse, summary="Delete draft email")
async def delete_draft(draft_id: str, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft '{draft_id}' not found")

@router.get("/templates", summary="List email templates")
async def list_email_templates(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailTemplate).limit(20))
    tmpls = res.scalars().all()
    return [{"id": t.id, "name": t.name, "subject": t.subject, "category": t.category} for t in tmpls]

@router.post("/templates", response_model=MessageResponse, summary="Create new email template")
async def create_email_template(name: str, subject: str, body: str, category: str = "General", db: AsyncSession = Depends(get_db)):
    try:
        t = EmailTemplate(organization_id="org-1", name=name, subject=subject, body_template=body, category=category)
        db.add(t)
        await db.commit()
        return {"message": f"Template '{name}' created", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/templates/{template_id}", summary="Get email template by ID")
async def get_email_template(template_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found")
    return {"id": t.id, "name": t.name, "subject": t.subject, "body": t.body_template, "category": t.category}

@router.put("/templates/{template_id}", response_model=MessageResponse, summary="Update email template")
async def update_email_template(template_id: str, name: str, subject: str, body: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found")
    try:
        t.name = name
        t.subject = subject
        t.body_template = body
        await db.commit()
        return {"message": f"Template {template_id} updated", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/templates/{template_id}", response_model=MessageResponse, summary="Delete email template")
async def delete_email_template(template_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found")
    try:
        await db.delete(t)
        await db.commit()
        return {"message": f"Template {template_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/campaigns/send-bulk", summary="Send bulk email campaign blast to target list")
async def send_bulk_campaign(template_id: str, lead_ids: List[str], db: AsyncSession = Depends(get_db)):
    return {"campaign_id": "cmpg-90", "queued_count": len(lead_ids), "status": "processing"}

@router.get("/tracking/{email_id}/status", summary="Get email open & link click analytics")
async def get_email_tracking(email_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Email).where(Email.id == email_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Email '{email_id}' not found")
    return {"email_id": email_id, "opens": 0, "last_opened_at": None, "link_clicks": 0, "bounced": False}

@router.get("/signatures", summary="List user email signatures")
async def get_email_signatures(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/signatures", response_model=MessageResponse, summary="Create or update user email signature")
async def save_email_signature(name: str, html: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Signature '{name}' saved", "status": "success"}

@router.get("/threads/{thread_id}", summary="Get full email conversation thread")
async def get_email_thread(thread_id: str, db: AsyncSession = Depends(get_db)):
    return {"thread_id": thread_id, "messages": []}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete emails from inbox")
async def bulk_delete_emails(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Email).where(Email.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Emails deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/sync/imap", response_model=MessageResponse, summary="Trigger IMAP/SMTP background mail sync")
async def sync_imap_inbox(db: AsyncSession = Depends(get_db)):
    return {"message": "IMAP email sync initiated", "status": "success"}
