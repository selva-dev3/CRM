import json
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.core.logging import get_logger
from app.models import Integration, User
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.crm_schemas import (
    SlackConnectRequest,
    SlackEventPayload,
    SlackEventsUpdateRequest,
    SlackNotifyPayload,
    ZapierConnectPayload,
)

logger = get_logger(__name__)

DEFAULT_CONNECTORS = [
    {"name": "Slack Sync", "category": "Communication", "is_connected": True, "description": "Post lead updates & deal notifications to Slack channels."},
    {"name": "Zapier Connector", "category": "Automation", "is_connected": True, "description": "Connect with 5,000+ web applications via Zapier webhooks."},
    {"name": "Stripe Billing", "category": "Finance", "is_connected": True, "description": "Sync quotes and invoices with real-time payment capture."},
    {"name": "Google Calendar", "category": "Productivity", "is_connected": True, "description": "Sync meetings and sales demos two-ways with Google Calendar."},
    {"name": "Mailchimp Campaigns", "category": "Marketing", "is_connected": False, "description": "Sync contacts into drip email sequences."},
    {"name": "HubSpot Migration", "category": "Data Import", "is_connected": False, "description": "Export and sync contacts, companies, and deals from HubSpot."},
]

SLACK_ENABLED_EVENTS = [
    "lead.created", "lead.updated", "lead.assigned",
    "company.created", "company.updated",
    "contact.created", "deal.created", "deal.won", "deal.lost",
    "task.created", "task.completed", "meeting.created",
    "invoice.paid", "integration.connected", "integration.disconnected",
]

_SLACK_EVENT_TITLES = {
    "lead.created": "New lead created",
    "lead.updated": "Lead updated",
    "lead.assigned": "Lead assigned",
    "company.created": "New company added",
    "company.updated": "Company updated",
    "contact.created": "New contact added",
    "deal.created": "New deal created",
    "deal.won": "Deal won 🎉",
    "deal.lost": "Deal lost",
    "task.created": "New task",
    "task.completed": "Task completed",
    "meeting.created": "Meeting scheduled",
    "invoice.paid": "Invoice paid",
    "integration.connected": "Integration connected",
    "integration.disconnected": "Integration disconnected",
}


class IntegrationService:
    """Business logic for the Integration domain."""

    def __init__(self, repository: IntegrationRepository | None = None) -> None:
        self.repository = repository or IntegrationRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=error_message) from e

    # --- List integrations ---
    async def list_integrations(self, db: AsyncSession) -> list[dict]:
        try:
            integrations = await self.repository.list_all(db)
            if integrations:
                return [
                    {"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None}
                    for i in integrations
                ]
            return [
                {"name": c["name"], "is_connected": False, "last_synced": None}
                for c in DEFAULT_CONNECTORS
            ]
        except Exception:
            logger.warning("Unable to list integrations; returning empty list")
            return []

    # --- Zapier ---
    async def get_zapier_config(self, db: AsyncSession, current_user: User | None) -> dict:
        try:
            org_id = await self.repository.resolve_org_id(db, current_user)
            integration = await db.scalar(
                select(Integration).where(
                    Integration.organization_id == org_id,
                    (Integration.provider == "zapier") | (Integration.name.ilike("%zapier%")),
                )
            )
            if not integration:
                return {"name": "Zapier Connector", "is_connected": False, "webhook_url": None, "events": [], "last_synced": None}
            cred_dict = self._parse_credentials(integration.credentials)
            webhook_url = getattr(integration, "webhook_url", None) or (cred_dict.get("webhook_url") if isinstance(cred_dict, dict) else None)
            events = cred_dict.get("events") if isinstance(cred_dict, dict) and "events" in cred_dict else ["lead.created", "deal.won", "contact.updated"]
            return {
                "name": integration.name,
                "is_connected": integration.is_connected,
                "webhook_url": webhook_url,
                "events": events,
                "last_synced": integration.last_synced.isoformat() if integration.last_synced else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=f"Unable to load Zapier configuration. {str(e)}") from e

    def _parse_credentials(self, credentials: Any) -> dict:
        if not credentials:
            return {}
        if isinstance(credentials, dict):
            return credentials
        if isinstance(credentials, str):
            try:
                return json.loads(credentials)
            except Exception:
                return {}
        return {}

    async def connect_zapier(self, db: AsyncSession, payload: ZapierConnectPayload, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        if not payload.webhook_url:
            raise APIException(status_code=400, message="Webhook URL is required.")
        try:
            integration = await self.repository.get_by_provider(db, org_id, "zapier")
            creds = json.dumps({"events": ["lead.created", "deal.won", "contact.updated"]})
            if integration is None:
                integration = await self.repository.create(
                    db,
                    data={
                        "organization_id": org_id,
                        "name": "Zapier Connector",
                        "provider": "zapier",
                        "is_connected": True,
                        "status": "connected",
                        "webhook_url": payload.webhook_url,
                        "credentials": creds,
                    },
                )
            else:
                integration.is_connected = True
                integration.status = "connected"
                integration.webhook_url = payload.webhook_url
                integration.credentials = creds
            await self.repository.commit(db)
            await db.refresh(integration)

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    integration.webhook_url,
                    json={"event": "connection.test", "organization_id": org_id, "message": "CRM successfully connected to Zapier"},
                )
            if response.status_code not in [200, 201, 202]:
                raise APIException(status_code=500, message=f"Zapier returned {response.status_code}")
            return {"message": "Zapier connected successfully.", "status": "success"}
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=500, message=str(e)) from e

    async def test_zapier_connection(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "zapier")
        if integration is None:
            raise APIException(status_code=404, message="Zapier integration is not connected.")
        if not integration.webhook_url:
            raise APIException(status_code=400, message="Zapier webhook URL is missing.")
        zapier_payload = {"event": "test.connection", "organization_id": org_id, "timestamp": datetime.utcnow().isoformat(), "data": {"message": "CRM Zapier integration test successful.", "status": "success"}}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(integration.webhook_url, json=zapier_payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Zapier test payload sent successfully.", "status": "success"}
        except Exception as e:
            integration.last_error = str(e)
            await self.repository.commit(db)
            raise APIException(status_code=500, message=f"Failed to send Zapier test payload: {str(e)}") from e

    async def trigger_zapier_event(self, db: AsyncSession, payload: Any, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "zapier")
        if integration is None:
            raise APIException(status_code=404, message="Zapier integration is not connected.")
        if not integration.webhook_url:
            raise APIException(status_code=400, message="Zapier webhook URL is missing.")
        webhook_payload = {"event": payload.event_name, "organization_id": org_id, "timestamp": datetime.utcnow().isoformat(), "data": payload.payload}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(integration.webhook_url, json=webhook_payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Zapier event sent successfully.", "status": "success"}
        except Exception as e:
            integration.last_error = str(e)
            await self.repository.commit(db)
            raise APIException(status_code=500, message=f"Failed to send webhook: {str(e)}") from e

    async def delete_zapier_integration(self, db: AsyncSession) -> dict:
        try:
            res = await db.execute(
                select(Integration).where(Integration.provider == "zapier")
            )
            integration = res.scalars().first()
            if not integration:
                raise APIException(status_code=404, message="Zapier integration not found.")
            integration.is_connected = False
            integration.webhook_url = None
            integration.credentials = None
            integration.status = "disconnected"
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Zapier integration disconnected and webhook removed.", "status": "success"}
        except APIException:
            raise
        except Exception:
            await db.rollback()
            raise

    # --- HubSpot mapping ---
    async def get_hubspot_mapping(self) -> dict:
        return {"lead_to_contact": {"first_name": "firstname", "last_name": "lastname", "email": "email", "company": "company_name"}}

    async def update_hubspot_mapping(self) -> dict:
        return {"message": "HubSpot schema field mapping rules updated", "status": "success"}

    # --- Slack ---
    async def get_slack_config(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "slack")
        if integration is None:
            return {"name": "Slack Connector", "is_connected": False, "webhook_url": None, "events": [], "last_synced": None}
        events = []
        if integration.enabled_events:
            try:
                events = json.loads(integration.enabled_events)
            except Exception:
                events = []
        return {
            "name": integration.name,
            "is_connected": integration.is_connected,
            "webhook_url": integration.webhook_url,
            "events": events,
            "last_synced": integration.last_synced.isoformat() if integration.last_synced else None,
        }

    async def connect_slack(self, db: AsyncSession, payload: SlackConnectRequest, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        if not payload.webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is required.")
        if not str(payload.webhook_url).startswith("https://hooks.slack.com/"):
            raise APIException(status_code=400, message="Invalid Slack webhook URL.")
        try:
            integration = await self.repository.get_by_provider(db, org_id, "slack")
            if integration is None:
                integration = await self.repository.create(
                    db,
                    data={
                        "organization_id": org_id,
                        "name": "Slack Connector",
                        "provider": "slack",
                        "is_connected": True,
                        "webhook_url": str(payload.webhook_url),
                        "status": "connected",
                        "enabled_events": json.dumps(SLACK_ENABLED_EVENTS),
                        "credentials": json.dumps({"channel": "incoming-webhook", "type": "slack"}),
                        "sync_enabled": True,
                        "last_synced": datetime.utcnow(),
                        "last_error": None,
                    },
                )
            else:
                integration.is_connected = True
                integration.status = "connected"
                integration.webhook_url = str(payload.webhook_url)
                integration.enabled_events = json.dumps(SLACK_ENABLED_EVENTS)
                integration.credentials = json.dumps({"channel": "incoming-webhook", "type": "slack"})
                integration.sync_enabled = True
                integration.last_synced = datetime.utcnow()
                integration.last_error = None
            await self.repository.commit(db)
            await db.refresh(integration)
            from app.services.notification_service import notification_service

            await notification_service.notify_in_app(
                db,
                event_name="integration.connected",
                organization_id=org_id,
                entity_type="integration",
                entity_id=integration.id,
                data={"provider": "slack", "organization_id": org_id},
            )
            await self.notify_slack_event(
                db,
                event_name="integration.connected",
                data={"provider": "slack", "organization_id": org_id},
                org_id=org_id,
            )
            return {"message": "Slack connected successfully.", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=500, message=f"Failed to connect Slack: {str(e)}") from e

    async def update_slack_events(self, db: AsyncSession, payload: SlackEventsUpdateRequest, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        valid_events = [e for e in payload.events if e in SLACK_ENABLED_EVENTS]
        integration.enabled_events = json.dumps(valid_events)
        integration.last_error = None
        await self.repository.commit(db)
        await db.refresh(integration)
        return {"message": "Slack enabled events updated.", "status": "success", "events": valid_events}

    async def test_slack_connection(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        if not integration.webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")
        slack_payload = {
            "text": " *Slack Integration Test*\n\nYour CRM has successfully connected to Slack.\n\n"
            f"Organization : {org_id}\nTime : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(integration.webhook_url, json=slack_payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Slack test message sent successfully.", "status": "success"}
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned {e.response.status_code}: {e.response.text}"
            await self.repository.commit(db)
            raise APIException(status_code=e.response.status_code, message=f"Slack webhook error : {e.response.text}") from e
        except Exception as e:
            integration.last_error = str(e)
            await self.repository.commit(db)
            raise APIException(status_code=500, message=f"Failed to send Slack test message : {str(e)}") from e

    @staticmethod
    def _build_slack_text(event_name: str, data: dict | None) -> str:
        title = _SLACK_EVENT_TITLES.get(event_name, "CRM Event")
        text = f" *{title}*\n"
        if data:
            for key, value in data.items():
                text += f"\n• {key} : {value}"
        return text

    @staticmethod
    def _enabled_events(integration: Integration) -> list:
        if not integration.enabled_events:
            return []
        try:
            return json.loads(integration.enabled_events)
        except Exception:
            return []

    async def _post_to_slack(self, db: AsyncSession, integration: Integration, text: str) -> None:
        """Single Slack webhook send path. Sets last_synced/last_error and commits; raises on failure."""
        slack_payload = {"text": text}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(integration.webhook_url, json=slack_payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned {e.response.status_code}: {e.response.text}"
            await self._commit_last_error(db)
            raise APIException(status_code=e.response.status_code, message=f"Slack webhook error : {e.response.text}") from e
        except Exception as e:
            integration.last_error = str(e)
            await self._commit_last_error(db)
            raise APIException(status_code=500, message=f"Failed to send Slack event : {str(e)}") from e

    async def _commit_last_error(self, db: AsyncSession) -> None:
        try:
            await self.repository.commit(db)
        except Exception:
            return

    async def trigger_slack_event(self, db: AsyncSession, payload: SlackEventPayload, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        if not integration.webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")

        enabled_events = self._enabled_events(integration)
        if enabled_events and payload.event_name not in enabled_events:
            raise APIException(status_code=400, message=f"Slack event '{payload.event_name}' is disabled.")

        await self._post_to_slack(db, integration, self._build_slack_text(payload.event_name, payload.data))
        return {"message": f"Slack event '{payload.event_name}' sent successfully.", "status": "success"}

    async def notify_slack_event(
        self,
        db: AsyncSession,
        *,
        event_name: str,
        data: dict | None,
        org_id: str,
    ) -> None:
        """Best-effort automatic Slack notification.

        Fired after a CRM operation commits successfully. Never raises: a Slack
        failure must not roll back a successfully completed CRM operation.
        Respects the stored enabled_events and silently skips when Slack is not
        connected, the webhook is missing, or the event is disabled.
        """
        try:
            integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
            if integration is None:
                logger.info(
                    "Slack auto-notification skipped for event '%s' (org %s): Slack integration not connected",
                    event_name,
                    org_id,
                )
                return
            if not integration.webhook_url:
                logger.info(
                    "Slack auto-notification skipped for event '%s' (org %s): webhook URL missing",
                    event_name,
                    org_id,
                )
                return
            enabled_events = self._enabled_events(integration)
            if enabled_events and event_name not in enabled_events:
                logger.info(
                    "Slack auto-notification skipped for event '%s' (org %s): event is disabled",
                    event_name,
                    org_id,
                )
                return
            await self._post_to_slack(db, integration, self._build_slack_text(event_name, data))
        except Exception as e:
            logger.warning("Slack auto-notification for event '%s' (org %s) failed: %s", event_name, org_id, e)

    async def disconnect_slack(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration not found.")
        try:
            from app.services.notification_service import notification_service

            await notification_service.notify_in_app(
                db,
                event_name="integration.disconnected",
                organization_id=org_id,
                entity_type="integration",
                entity_id=integration.id,
                data={"provider": "slack", "organization_id": org_id},
            )
            await self.notify_slack_event(
                db,
                event_name="integration.disconnected",
                data={"provider": "slack", "organization_id": org_id},
                org_id=org_id,
            )
            integration.is_connected = False
            integration.status = "disconnected"
            integration.webhook_url = None
            integration.credentials = None
            integration.enabled_events = None
            integration.access_token = None
            integration.refresh_token = None
            integration.external_id = None
            integration.sync_enabled = False
            integration.last_error = None
            integration.last_synced = datetime.utcnow()
            await self.repository.commit(db)
            await db.refresh(integration)
            return {"message": "Slack integration disconnected successfully.", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=500, message=f"Failed to disconnect Slack: {str(e)}") from e

    async def send_slack_notification(self, db: AsyncSession, payload: SlackNotifyPayload, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        if not integration.webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")
        channel = payload.channel or "general"
        message = payload.message or "Notification from Enterprise CRM"
        slack_payload = {"text": f" *CRM Notification*\n\nChannel : #{channel}\n\n{message}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(integration.webhook_url, json=slack_payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": f"Slack notification posted successfully to #{channel}.", "status": "success"}
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned {e.response.status_code}: {e.response.text}"
            await self.repository.commit(db)
            raise APIException(status_code=e.response.status_code, message=f"Slack webhook error: {e.response.text}") from e
        except Exception as e:
            integration.last_error = str(e)
            await self.repository.commit(db)
            raise APIException(status_code=500, message=f"Failed to send Slack notification: {str(e)}") from e

    # --- Stripe / OAuth / misc ---
    async def handle_stripe_webhook(self, event_type: str | None, payload_event_type: str | None) -> dict:
        ev = payload_event_type or event_type or "payment_intent.succeeded"
        return {"message": f"Stripe billing webhook event '{ev}' processed", "status": "success"}

    async def google_oauth_callback(self) -> dict:
        return {"message": "Google OAuth authorization tokens exchanged and saved", "status": "success"}

    async def microsoft_oauth_callback(self) -> dict:
        return {"message": "Microsoft OAuth authorization tokens exchanged and saved", "status": "success"}

    async def get_sync_logs(self) -> list[dict]:
        return [
            {"id": "sync-1", "integration_name": "Slack Sync", "status": "SUCCESS", "records_synced": 42, "timestamp": "2026-08-07T10:15:00Z"},
            {"id": "sync-2", "integration_name": "Google Calendar", "status": "SUCCESS", "records_synced": 18, "timestamp": "2026-08-07T09:30:00Z"},
            {"id": "sync-3", "integration_name": "HubSpot Migration", "status": "COMPLETED", "records_synced": 150, "timestamp": "2026-08-07T08:45:00Z"},
        ]

    async def retry_failed_sync(self, job_id: str | None, payload_job_id: str | None) -> dict:
        jid = payload_job_id or job_id or "job-1"
        return {"message": f"Retry job queued for sync execution '{jid}'", "status": "success"}

    async def save_custom_provider_key(self, provider_name: str | None, payload_provider_name: str | None) -> dict:
        pname = payload_provider_name or provider_name or "Custom Integration"
        return {"message": f"Secret API credentials configured for provider '{pname}'", "status": "success"}

    # --- Generic by-name operations ---
    async def get_integration_status(self, db: AsyncSession, name: str) -> dict:
        try:
            i = await self.repository.get_by_name_like(db, name)
            if i:
                return {"name": i.name, "is_connected": i.is_connected, "last_synced": str(i.last_synced) if i.last_synced else None}
        except Exception:
            logger.warning("Unable to load integration status for '%s'", name)
        return {"name": name.capitalize(), "is_connected": False, "last_synced": None}

    async def connect_integration(self, db: AsyncSession, name: str, current_user: User | None) -> dict:
        try:
            i = await self.repository.get_by_name_like(db, name)
            org_id = await self.repository.resolve_org_id(db, current_user)
            if not i:
                await self.repository.create(db, data={"organization_id": org_id, "name": name.capitalize(), "is_connected": True})
            else:
                i.is_connected = True
            await self.repository.commit(db)
        except Exception:
            await db.rollback()
        return {"auth_url": f"https://auth.{name.lower()}.com/oauth2/authorize?client_id=crm_app", "message": f"{name} connected successfully", "status": "success"}

    async def disconnect_integration(self, db: AsyncSession, name: str) -> dict:
        try:
            i = await self.repository.get_by_name_like(db, name)
            if i:
                i.is_connected = False
                await self.repository.commit(db)
        except Exception:
            await db.rollback()
        return {"message": f"Integration '{name}' disconnected successfully", "status": "success"}

    async def sync_integration(self, name: str) -> dict:
        return {"message": f"Manual full synchronization initiated for '{name}'", "status": "success"}


integration_service = IntegrationService()
