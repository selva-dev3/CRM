from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import EmailResponse, EmailSendRequest

router = APIRouter()

@router.get("/", response_model=List[EmailResponse], summary="List email inbox threads")
async def list_emails():
    return [
        {"id": "eml-1", "from_email": "sales@crm.com", "to": ["john@acme.com"], "subject": "Proposal details", "sent_at": "2026-08-01T09:00:00Z"}
    ]

@router.post("/send", response_model=EmailResponse, status_code=201, summary="Send email")
async def send_email(payload: EmailSendRequest):
    return {"id": "eml-2", "from_email": "sales@crm.com", "to": [str(e) for e in payload.to], "subject": payload.subject, "sent_at": "2026-08-02T12:00:00Z"}
