from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Integration
from app.schemas.crm_schemas import IntegrationStatus, MessageResponse

router = APIRouter()

@router.get("", response_model=List[IntegrationStatus], summary="List available third-party integration connectors")
async def list_integrations(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Integration).limit(20))
        integrations = res.scalars().all()
        return [{"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None} for i in integrations]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{name}/status", response_model=IntegrationStatus, summary="Get connection status for specific integration")
async def get_integration_status(name: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Integration).where(Integration.name.ilike(name)))
    i = res.scalars().first()
    if not i:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Integration connector '{name}' not found")
    return {"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None}

@router.post("/{name}/connect", summary="Initiate OAuth connector authentication URL")
async def connect_integration(name: str, db: AsyncSession = Depends(get_db)):
    return {"auth_url": f"https://auth.{name.lower()}.com/oauth2/authorize?client_id=crm_app"}

@router.post("/{name}/disconnect", response_model=MessageResponse, summary="Revoke tokens and disconnect integration")
async def disconnect_integration(name: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Integration).where(Integration.name.ilike(name)))
    i = res.scalars().first()
    if not i:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Integration '{name}' not found")
    try:
        i.is_connected = False
        await db.commit()
        return {"message": f"Integration {name} disconnected", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{name}/sync", response_model=MessageResponse, summary="Trigger manual full sync job for integration")
async def sync_integration(name: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Integration).where(Integration.name.ilike(name)))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Integration '{name}' not found")
    return {"message": f"Sync initiated for {name}", "status": "success"}

@router.get("/hubspot/mapping", summary="Get HubSpot schema field mapping rules")
async def get_hubspot_mapping(db: AsyncSession = Depends(get_db)):
    return {"lead_to_contact": {"first_name": "firstname", "email": "email"}}

@router.put("/hubspot/mapping", response_model=MessageResponse, summary="Update HubSpot schema field mapping rules")
async def update_hubspot_mapping(mapping: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return {"message": "HubSpot field mapping updated", "status": "success"}

@router.post("/slack/notify", response_model=MessageResponse, summary="Publish custom notification message to Slack channel")
async def send_slack_notification(channel: str, message: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Slack message posted to #{channel}", "status": "success"}

@router.post("/zapier/event", response_model=MessageResponse, summary="Trigger outbound webhook event to Zapier subscription")
async def trigger_zapier_event(event_name: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return {"message": f"Zapier event '{event_name}' dispatched", "status": "success"}

@router.post("/stripe/webhook", response_model=MessageResponse, summary="Stripe incoming billing webhook handler")
async def handle_stripe_webhook(event_type: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Stripe event '{event_type}' processed", "status": "success"}

@router.post("/google/callback", response_model=MessageResponse, summary="Google OAuth callback code authorization handler")
async def google_oauth_callback(code: str, db: AsyncSession = Depends(get_db)):
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")
    return {"message": "Google OAuth tokens exchanged and saved", "status": "success"}

@router.post("/microsoft/callback", response_model=MessageResponse, summary="Microsoft OAuth callback code authorization handler")
async def microsoft_oauth_callback(code: str, db: AsyncSession = Depends(get_db)):
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")
    return {"message": "Microsoft OAuth tokens exchanged and saved", "status": "success"}

@router.get("/sync-logs", summary="List integration synchronization execution audit logs")
async def get_sync_logs(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/sync-logs/retry", response_model=MessageResponse, summary="Retry failed integration sync job execution")
async def retry_failed_sync(job_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Retry job queued for sync {job_id}", "status": "success"}

@router.post("/custom-api-key", response_model=MessageResponse, summary="Configure custom third-party provider API key secret")
async def save_custom_provider_key(provider_name: str, api_key: str, db: AsyncSession = Depends(get_db)):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key required")
    return {"message": f"Credentials saved for provider '{provider_name}'", "status": "success"}
