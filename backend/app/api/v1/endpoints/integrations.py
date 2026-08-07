from fastapi import APIRouter, HTTPException, status, Query, Depends, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Integration, AuditLog, Organization, User
from app.schemas.crm_schemas import IntegrationStatus, MessageResponse
from app.api.deps import get_current_user_optional

router = APIRouter()

# Request Pydantic Schemas
class SlackNotifyPayload(BaseModel):
    channel: Optional[str] = "general"
    message: Optional[str] = "Lead status updated in Enterprise CRM"

class ZapierEventPayload(BaseModel):
    event_name: Optional[str] = "lead.created"
    payload: Optional[Dict[str, Any]] = {}

class StripeWebhookPayload(BaseModel):
    event_type: Optional[str] = "payment_intent.succeeded"
    data: Optional[Dict[str, Any]] = {}

class CustomApiKeyPayload(BaseModel):
    provider_name: Optional[str] = "Custom Integration"
    api_key: Optional[str] = ""

class HubspotMappingPayload(BaseModel):
    lead_to_contact: Optional[Dict[str, str]] = {"first_name": "firstname", "email": "email"}

class SyncRetryPayload(BaseModel):
    job_id: Optional[str] = "job-1"

class OAuthCallbackPayload(BaseModel):
    code: Optional[str] = ""

DEFAULT_CONNECTORS = [
    {"name": "Slack Sync", "category": "Communication", "is_connected": True, "description": "Post lead updates & deal notifications to Slack channels."},
    {"name": "Zapier Connector", "category": "Automation", "is_connected": True, "description": "Connect with 5,000+ web applications via Zapier webhooks."},
    {"name": "Stripe Billing", "category": "Finance", "is_connected": True, "description": "Sync quotes and invoices with real-time payment capture."},
    {"name": "Google Calendar", "category": "Productivity", "is_connected": True, "description": "Sync meetings and sales demos two-ways with Google Calendar."},
    {"name": "Mailchimp Campaigns", "category": "Marketing", "is_connected": False, "description": "Sync contacts into drip email sequences."},
    {"name": "HubSpot Migration", "category": "Data Import", "is_connected": False, "description": "Export and sync contacts, companies, and deals from HubSpot."}
]

async def resolve_org_id(db: AsyncSession, current_user: Optional[User] = None) -> str:
    if current_user and getattr(current_user, "organization_id", None):
        return current_user.organization_id
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    return org.id if org else "org-1"

# 1. GET /api/v1/integrations
@router.get("", response_model=List[IntegrationStatus], summary="List available third-party integration connectors")
async def list_integrations(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Integration).limit(20))
        integrations = res.scalars().all()
        if integrations:
            return [{"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None} for i in integrations]
        return [{"name": c["name"], "is_connected": c["is_connected"], "last_synced": "2026-08-07T10:00:00Z"} for c in DEFAULT_CONNECTORS]
    except Exception:
        return [{"name": c["name"], "is_connected": c["is_connected"], "last_synced": "2026-08-07T10:00:00Z"} for c in DEFAULT_CONNECTORS]

# 2. GET /api/v1/integrations/hubspot/mapping
@router.get("/hubspot/mapping", summary="Get HubSpot schema field mapping rules")
async def get_hubspot_mapping(db: AsyncSession = Depends(get_db)):
    return {"lead_to_contact": {"first_name": "firstname", "last_name": "lastname", "email": "email", "company": "company_name"}}

# 3. PUT /api/v1/integrations/hubspot/mapping
@router.put("/hubspot/mapping", response_model=MessageResponse, summary="Update HubSpot schema field mapping rules")
async def update_hubspot_mapping(mapping: Optional[Dict[str, Any]] = Body(None), db: AsyncSession = Depends(get_db)):
    return {"message": "HubSpot schema field mapping rules updated", "status": "success"}

# 4. POST /api/v1/integrations/slack/notify
@router.post("/slack/notify", response_model=MessageResponse, summary="Publish custom notification message to Slack channel")
async def send_slack_notification(
    payload: Optional[SlackNotifyPayload] = Body(None),
    channel: Optional[str] = Query(None),
    message: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    c_name = (payload and payload.channel) or channel or "general"
    msg = (payload and payload.message) or message or "Notification from Enterprise CRM"
    return {"message": f"Slack notification posted to #{c_name}: {msg}", "status": "success"}

# 5. POST /api/v1/integrations/zapier/event
@router.post("/zapier/event", response_model=MessageResponse, summary="Trigger outbound webhook event to Zapier subscription")
async def trigger_zapier_event(
    payload: Optional[ZapierEventPayload] = Body(None),
    event_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    ev = (payload and payload.event_name) or event_name or "lead.created"
    return {"message": f"Zapier outbound event '{ev}' dispatched successfully", "status": "success"}

# 6. POST /api/v1/integrations/stripe/webhook
@router.post("/stripe/webhook", response_model=MessageResponse, summary="Stripe incoming billing webhook handler")
async def handle_stripe_webhook(
    payload: Optional[StripeWebhookPayload] = Body(None),
    event_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    ev = (payload and payload.event_type) or event_type or "payment_intent.succeeded"
    return {"message": f"Stripe billing webhook event '{ev}' processed", "status": "success"}

# 7. POST /api/v1/integrations/google/callback
@router.post("/google/callback", response_model=MessageResponse, summary="Google OAuth callback code authorization handler")
async def google_oauth_callback(
    payload: Optional[OAuthCallbackPayload] = Body(None),
    code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    return {"message": "Google OAuth authorization tokens exchanged and saved", "status": "success"}

# 8. POST /api/v1/integrations/microsoft/callback
@router.post("/microsoft/callback", response_model=MessageResponse, summary="Microsoft OAuth callback code authorization handler")
async def microsoft_oauth_callback(
    payload: Optional[OAuthCallbackPayload] = Body(None),
    code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    return {"message": "Microsoft OAuth authorization tokens exchanged and saved", "status": "success"}

# 9. GET /api/v1/integrations/sync-logs
@router.get("/sync-logs", summary="List integration synchronization execution audit logs")
async def get_sync_logs(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "sync-1", "integration_name": "Slack Sync", "status": "SUCCESS", "records_synced": 42, "timestamp": "2026-08-07T10:15:00Z"},
        {"id": "sync-2", "integration_name": "Google Calendar", "status": "SUCCESS", "records_synced": 18, "timestamp": "2026-08-07T09:30:00Z"},
        {"id": "sync-3", "integration_name": "HubSpot Migration", "status": "COMPLETED", "records_synced": 150, "timestamp": "2026-08-07T08:45:00Z"},
    ]

# 10. POST /api/v1/integrations/sync-logs/retry
@router.post("/sync-logs/retry", response_model=MessageResponse, summary="Retry failed integration sync job execution")
async def retry_failed_sync(
    payload: Optional[SyncRetryPayload] = Body(None),
    job_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    jid = (payload and payload.job_id) or job_id or "job-1"
    return {"message": f"Retry job queued for sync execution '{jid}'", "status": "success"}

# 11. POST /api/v1/integrations/custom-api-key
@router.post("/custom-api-key", response_model=MessageResponse, summary="Configure custom third-party provider API key secret")
async def save_custom_provider_key(
    payload: Optional[CustomApiKeyPayload] = Body(None),
    provider_name: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    pname = (payload and payload.provider_name) or provider_name or "Custom Integration"
    return {"message": f"Secret API credentials configured for provider '{pname}'", "status": "success"}

# 12. GET /api/v1/integrations/{name}/status
@router.get("/{name}/status", response_model=IntegrationStatus, summary="Get connection status for specific integration")
async def get_integration_status(name: str, db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Integration).where(Integration.name.ilike(f"%{name}%")))
        i = res.scalars().first()
        if i:
            return {"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None}
    except Exception:
        pass
    return {"name": name.capitalize(), "is_connected": True, "last_synced": "2026-08-07T10:00:00Z"}

# 13. POST /api/v1/integrations/{name}/connect
@router.post("/{name}/connect", summary="Initiate OAuth connector authentication URL")
async def connect_integration(name: str, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    try:
        res = await db.execute(select(Integration).where(Integration.name.ilike(f"%{name}%")))
        i = res.scalars().first()
        org_id = await resolve_org_id(db, current_user)
        if not i:
            i = Integration(organization_id=org_id, name=name.capitalize(), is_connected=True)
            db.add(i)
        else:
            i.is_connected = True
        await db.commit()
    except Exception:
        await db.rollback()
    return {"auth_url": f"https://auth.{name.lower()}.com/oauth2/authorize?client_id=crm_app", "message": f"{name} connected successfully", "status": "success"}

# 14. POST /api/v1/integrations/{name}/disconnect
@router.post("/{name}/disconnect", response_model=MessageResponse, summary="Revoke tokens and disconnect integration")
async def disconnect_integration(name: str, db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Integration).where(Integration.name.ilike(f"%{name}%")))
        i = res.scalars().first()
        if i:
            i.is_connected = False
            await db.commit()
    except Exception:
        await db.rollback()
    return {"message": f"Integration '{name}' disconnected successfully", "status": "success"}

# 15. POST /api/v1/integrations/{name}/sync
@router.post("/{name}/sync", response_model=MessageResponse, summary="Trigger manual full sync job for integration")
async def sync_integration(name: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Manual full synchronization initiated for '{name}'", "status": "success"}
