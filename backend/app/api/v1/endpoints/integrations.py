from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import IntegrationStatus

router = APIRouter()

@router.get("/", response_model=List[IntegrationStatus], summary="List external integrations & status")
async def list_integrations():
    return [
        {"name": "Gmail API", "is_connected": True, "last_synced": "2026-08-02T11:30:00Z"},
        {"name": "Google Calendar", "is_connected": True, "last_synced": "2026-08-02T11:30:00Z"},
        {"name": "Slack", "is_connected": True, "last_synced": "2026-08-02T10:00:00Z"},
        {"name": "Zoom", "is_connected": False, "last_synced": None},
        {"name": "Stripe Payments", "is_connected": True, "last_synced": "2026-08-02T12:00:00Z"},
        {"name": "Twilio Telephony", "is_connected": True, "last_synced": "2026-08-02T08:00:00Z"},
        {"name": "WhatsApp Business", "is_connected": False, "last_synced": None},
        {"name": "OpenAI / Claude API", "is_connected": True, "last_synced": "2026-08-02T12:00:00Z"},
    ]
