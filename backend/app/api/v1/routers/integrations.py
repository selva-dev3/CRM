from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user_optional, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    IntegrationStatus,
    MessageResponse,
    SlackConfigResponse,
    SlackConnectRequest,
    SlackEventPayload,
    SlackEventsUpdateRequest,
    SlackNotifyPayload,
    ZapierConnectPayload,
)
from app.services.integration_service import integration_service

router = APIRouter()


class ZapierEventPayload(BaseModel):
    event_name: str | None = None
    payload: dict[str, Any] | None = None


class StripeWebhookPayload(BaseModel):
    event_type: str | None = "payment_intent.succeeded"
    data: dict[str, Any] | None = {}


class CustomApiKeyPayload(BaseModel):
    provider_name: str | None = "Custom Integration"
    api_key: str | None = ""


class OAuthCallbackPayload(BaseModel):
    code: str | None = ""


class SyncRetryPayload(BaseModel):
    job_id: str | None = "job-1"


@router.get(
    "",
    response_model=list[IntegrationStatus],
    summary="List available third-party integration connectors",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def list_integrations(db: AsyncSession = Depends(get_db)):
    return await integration_service.list_integrations(db)


@router.get(
    "/zapier",
    summary="Get Zapier integration status and configuration",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def get_zapier_config(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.get_zapier_config(db, current_user)


@router.post(
    "/zapier/connect",
    response_model=MessageResponse,
    summary="Connect Zapier webhook",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def connect_zapier(
    payload: ZapierConnectPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.connect_zapier(db, payload, current_user)


@router.post(
    "/zapier/test",
    response_model=MessageResponse,
    summary="Send test payload to Zapier webhook",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def test_zapier_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.test_zapier_connection(db, current_user)


@router.post(
    "/zapier/event",
    response_model=MessageResponse,
    summary="Trigger outbound webhook event to Zapier subscription",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def trigger_zapier_event(
    payload: ZapierEventPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.trigger_zapier_event(db, payload, current_user)


@router.delete(
    "/zapier",
    response_model=MessageResponse,
    summary="Disconnect and revoke Zapier integration configuration",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def delete_zapier_integration(db: AsyncSession = Depends(get_db)):
    return await integration_service.delete_zapier_integration(db)


@router.get(
    "/hubspot/mapping",
    summary="Get HubSpot schema field mapping rules",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def get_hubspot_mapping(db: AsyncSession = Depends(get_db)):
    return await integration_service.get_hubspot_mapping()


@router.put(
    "/hubspot/mapping",
    response_model=MessageResponse,
    summary="Update HubSpot schema field mapping rules",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def update_hubspot_mapping(
    mapping: dict[str, Any] | None = Body(None), db: AsyncSession = Depends(get_db)
):
    return await integration_service.update_hubspot_mapping()


@router.get(
    "/slack",
    response_model=SlackConfigResponse,
    summary="Get Slack integration status and configuration",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def get_slack_config(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.get_slack_config(db, current_user)


@router.post(
    "/slack/connect",
    response_model=MessageResponse,
    summary="Connect Slack Incoming Webhook",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def connect_slack(
    payload: SlackConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.connect_slack(db, payload, current_user)


@router.post(
    "/slack/test",
    response_model=MessageResponse,
    summary="Send test message to Slack webhook",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def test_slack_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.test_slack_connection(db, current_user)


@router.put(
    "/slack/events",
    response_model=MessageResponse,
    summary="Configure enabled Slack notification events",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def update_slack_events(
    payload: SlackEventsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.update_slack_events(db, payload, current_user)


@router.post(
    "/slack/event",
    response_model=MessageResponse,
    summary="Trigger Slack notification event",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def trigger_slack_event(
    payload: SlackEventPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.trigger_slack_event(db, payload, current_user)


@router.delete(
    "/slack",
    response_model=MessageResponse,
    summary="Disconnect Slack integration",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def disconnect_slack(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.disconnect_slack(db, current_user)


@router.post(
    "/slack/notify",
    response_model=MessageResponse,
    summary="Publish custom notification message to Slack",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def send_slack_notification(
    payload: SlackNotifyPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.send_slack_notification(db, payload, current_user)


@router.post(
    "/stripe/webhook",
    response_model=MessageResponse,
    summary="Stripe incoming billing webhook handler",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def handle_stripe_webhook(
    payload: StripeWebhookPayload | None = Body(None),
    event_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await integration_service.handle_stripe_webhook(
        event_type, payload.event_type if payload else None
    )


@router.post(
    "/google/callback",
    response_model=MessageResponse,
    summary="Google OAuth callback code authorization handler",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def google_oauth_callback(
    payload: OAuthCallbackPayload | None = Body(None),
    code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await integration_service.google_oauth_callback()


@router.post(
    "/microsoft/callback",
    response_model=MessageResponse,
    summary="Microsoft OAuth callback code authorization handler",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def microsoft_oauth_callback(
    payload: OAuthCallbackPayload | None = Body(None),
    code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await integration_service.microsoft_oauth_callback()


@router.get(
    "/sync-logs",
    summary="List integration synchronization execution audit logs",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def get_sync_logs(db: AsyncSession = Depends(get_db)):
    return await integration_service.get_sync_logs()


@router.post(
    "/sync-logs/retry",
    response_model=MessageResponse,
    summary="Retry failed integration sync job execution",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def retry_failed_sync(
    payload: SyncRetryPayload | None = Body(None),
    job_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await integration_service.retry_failed_sync(job_id, payload.job_id if payload else None)


@router.post(
    "/custom-api-key",
    response_model=MessageResponse,
    summary="Configure custom third-party provider API key secret",
    dependencies=[Depends(require_permission("integrations:apikeys"))],
)
async def save_custom_provider_key(
    payload: CustomApiKeyPayload | None = Body(None),
    provider_name: str | None = Query(None),
    api_key: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await integration_service.save_custom_provider_key(
        provider_name, payload.provider_name if payload else None
    )


@router.get(
    "/{name}/status",
    response_model=IntegrationStatus,
    summary="Get connection status for specific integration",
    dependencies=[Depends(require_permission("integrations:read"))],
)
async def get_integration_status(name: str, db: AsyncSession = Depends(get_db)):
    return await integration_service.get_integration_status(db, name)


@router.post(
    "/{name}/connect",
    summary="Initiate OAuth connector authentication URL",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def connect_integration(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await integration_service.connect_integration(db, name, current_user)


@router.post(
    "/{name}/disconnect",
    response_model=MessageResponse,
    summary="Revoke tokens and disconnect integration",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def disconnect_integration(name: str, db: AsyncSession = Depends(get_db)):
    return await integration_service.disconnect_integration(db, name)


@router.post(
    "/{name}/sync",
    response_model=MessageResponse,
    summary="Trigger manual full sync job for integration",
    dependencies=[Depends(require_permission("integrations:manage"))],
)
async def sync_integration(name: str, db: AsyncSession = Depends(get_db)):
    return await integration_service.sync_integration(name)
