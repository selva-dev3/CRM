from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import (
    EmailSendRequest, EmailResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("/inbox", response_model=List[EmailResponse], summary="Fetch unified inbox email messages")
async def get_inbox(page: int = 1, limit: int = 20, folder: str = "inbox"):
    return [
        {"id": "eml-101", "from_email": "alice@techcorp.com", "to": ["usr-1@company.com"], "subject": "Re: Contract Terms Review", "sent_at": "2026-08-02T11:20:00Z"},
        {"id": "eml-102", "from_email": "bob@globalsolutions.com", "to": ["usr-1@company.com"], "subject": "Inquiry on pricing tier", "sent_at": "2026-08-02T08:45:00Z"}
    ]

@router.post("/send", response_model=EmailResponse, status_code=status.HTTP_201_CREATED, summary="Send single outbound email")
async def send_email(payload: EmailSendRequest):
    return {"id": "eml-103", "from_email": "usr-1@company.com", "to": [str(x) for x in payload.to], "subject": payload.subject, "sent_at": "2026-08-02T16:00:00Z"}

@router.get("/drafts", response_model=List[EmailResponse], summary="List saved email drafts")
async def list_drafts():
    return [{"id": "dft-1", "from_email": "usr-1@company.com", "to": ["lead@acme.com"], "subject": "[Draft] Follow up", "sent_at": "2026-08-02"}]

@router.post("/drafts", response_model=MessageResponse, summary="Save draft email message")
async def save_draft(payload: EmailSendRequest):
    return {"message": "Email draft saved", "status": "success"}

@router.get("/drafts/{draft_id}", response_model=EmailResponse, summary="Get draft email by ID")
async def get_draft(draft_id: str):
    return {"id": draft_id, "from_email": "usr-1@company.com", "to": ["lead@acme.com"], "subject": "[Draft] Follow up", "sent_at": "2026-08-02"}

@router.delete("/drafts/{draft_id}", response_model=MessageResponse, summary="Delete draft email")
async def delete_draft(draft_id: str):
    return {"message": f"Draft {draft_id} deleted", "status": "success"}

@router.get("/templates", summary="List email templates")
async def list_email_templates():
    return [
        {"id": "tmpl-1", "name": "Cold Outreach V1", "subject": "Quick question about {{company}}", "category": "Sales"},
        {"id": "tmpl-2", "name": "Demo Follow-Up", "subject": "Next steps following our call", "category": "Follow Up"}
    ]

@router.post("/templates", response_model=MessageResponse, summary="Create new email template")
async def create_email_template(name: str, subject: str, body: str, category: str = "General"):
    return {"message": f"Template '{name}' created", "status": "success"}

@router.get("/templates/{template_id}", summary="Get email template by ID")
async def get_email_template(template_id: str):
    return {"id": template_id, "name": "Cold Outreach V1", "subject": "Quick question about {{company}}", "body": "Hi {{first_name}}, ...", "category": "Sales"}

@router.put("/templates/{template_id}", response_model=MessageResponse, summary="Update email template")
async def update_email_template(template_id: str, name: str, subject: str, body: str):
    return {"message": f"Template {template_id} updated", "status": "success"}

@router.delete("/templates/{template_id}", response_model=MessageResponse, summary="Delete email template")
async def delete_email_template(template_id: str):
    return {"message": f"Template {template_id} deleted", "status": "success"}

@router.post("/campaigns/send-bulk", summary="Send bulk email campaign blast to target list")
async def send_bulk_campaign(template_id: str, lead_ids: List[str]):
    return {"campaign_id": "cmpg-90", "queued_count": len(lead_ids), "status": "processing"}

@router.get("/tracking/{email_id}/status", summary="Get email open & link click analytics")
async def get_email_tracking(email_id: str):
    return {"email_id": email_id, "opens": 3, "last_opened_at": "2026-08-02T14:10:00Z", "link_clicks": 1, "bounced": False}

@router.get("/signatures", summary="List user email signatures")
async def get_email_signatures():
    return [{"id": "sig-1", "name": "Default Signature", "html": "<b>John Doe</b><br>VP Sales"}]

@router.post("/signatures", response_model=MessageResponse, summary="Create or update user email signature")
async def save_email_signature(name: str, html: str):
    return {"message": f"Signature '{name}' saved", "status": "success"}

@router.get("/threads/{thread_id}", summary="Get full email conversation thread")
async def get_email_thread(thread_id: str):
    return {"thread_id": thread_id, "messages": [{"id": "eml-101", "subject": "Contract Review"}]}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete emails from inbox")
async def bulk_delete_emails(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Emails deleted"}

@router.post("/sync/imap", response_model=MessageResponse, summary="Trigger IMAP/SMTP background mail sync")
async def sync_imap_inbox():
    return {"message": "IMAP email sync initiated", "status": "success"}
