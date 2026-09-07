import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import get_logger
from app.core.security import ALGORITHM
from app.models import Integration, User
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.crm_schemas import (
    MailchimpConnectPayload,
    SlackConnectRequest,
    SlackEventPayload,
    SlackEventsUpdateRequest,
    SlackNotifyPayload,
    ZapierConnectPayload,
)

logger = get_logger(__name__)

DEFAULT_CONNECTORS = [
    {
        "name": "Slack Sync",
        "category": "Communication",
        "is_connected": False,
        "description": "Connect Slack before delivering CRM notifications.",
    },
    {
        "name": "Zapier Connector",
        "category": "Automation",
        "is_connected": False,
        "description": "Deliver CRM events to a configured Zapier webhook.",
    },
    {
        "name": "Google Calendar",
        "category": "Productivity",
        "is_connected": False,
        "description": "OAuth authentication is available; calendar synchronization is not.",
    },
    {
        "name": "Mailchimp Campaigns",
        "category": "Marketing",
        "is_connected": False,
        "description": "Sync contacts into drip email sequences.",
    },
    {
        "name": "HubSpot Migration",
        "category": "Data Import",
        "is_connected": False,
        "description": "Export and sync contacts, companies, and deals from HubSpot.",
    },
]

SLACK_ENABLED_EVENTS = [
    "lead.created",
    "lead.updated",
    "lead.assigned",
    "company.created",
    "company.updated",
    "contact.created",
    "deal.created",
    "deal.won",
    "deal.lost",
    "task.created",
    "task.completed",
    "meeting.created",
    "invoice.paid",
    "integration.connected",
    "integration.disconnected",
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
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    # --- List integrations ---
    async def list_integrations(self, db: AsyncSession, current_user: User) -> list[dict]:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integrations = await self.repository.list_all(db, org_id)
        if integrations:
            return [self._status_dict(i) for i in integrations]
        return [
            {
                "name": c["name"],
                "is_connected": False,
                "connection_status": "disconnected",
                "sync_status": "not_synced",
                "last_synced": None,
                "last_error": None,
            }
            for c in DEFAULT_CONNECTORS
        ]

    @staticmethod
    def _status_dict(integration: Integration) -> dict:
        raw_status = (integration.status or "disconnected").lower()
        sync_status = raw_status if raw_status in {"syncing", "synced", "sync_failed"} else "not_synced"
        connection_status = (
            "disconnected"
            if not integration.is_connected
            else "authenticated"
            if raw_status == "authenticated"
            else "connected"
        )
        return {
            "name": integration.name,
            "is_connected": integration.is_connected,
            "connection_status": connection_status,
            "sync_status": sync_status,
            "last_synced": integration.last_synced.isoformat()
            if integration.last_synced
            else None,
            "last_error": integration.last_error,
        }

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
                return {
                    "name": "Zapier Connector",
                    "is_connected": False,
                    "webhook_url": None,
                    "events": [],
                    "last_synced": None,
                }
            cred_dict = self._parse_credentials(integration.credentials)
            events = (
                cred_dict.get("events")
                if isinstance(cred_dict, dict) and "events" in cred_dict
                else ["lead.created", "deal.won", "contact.updated"]
            )
            return {
                "name": integration.name,
                "is_connected": integration.is_connected,
                "webhook_url": None,
                "events": events,
                "last_synced": integration.last_synced.isoformat()
                if integration.last_synced
                else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to load Zapier configuration.",
            ) from e

    @staticmethod
    def _secret_cipher() -> Fernet:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
        return Fernet(key)

    @classmethod
    def _encrypt_secret(cls, value: str) -> str:
        return "enc:v1:" + cls._secret_cipher().encrypt(value.encode()).decode()

    @classmethod
    def _decrypt_secret(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not value.startswith("enc:v1:"):
            return value
        try:
            return cls._secret_cipher().decrypt(value[7:].encode()).decode()
        except InvalidToken:
            return None

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

    @staticmethod
    def _oauth_settings(provider: str) -> tuple[str | None, str | None, str | None, str]:
        values = {
            "google": (
                settings.GOOGLE_OAUTH_CLIENT_ID,
                settings.GOOGLE_OAUTH_CLIENT_SECRET,
                settings.GOOGLE_CALENDAR_REDIRECT_URI,
                "https://accounts.google.com/o/oauth2/v2/auth",
            ),
            "hubspot": (
                settings.HUBSPOT_CLIENT_ID,
                settings.HUBSPOT_CLIENT_SECRET,
                settings.HUBSPOT_REDIRECT_URI,
                "https://app.hubspot.com/oauth/authorize",
            ),
            "slack": (
                settings.SLACK_CLIENT_ID,
                settings.SLACK_CLIENT_SECRET,
                settings.SLACK_REDIRECT_URI,
                "https://slack.com/oauth/v2/authorize",
            ),
        }
        if provider not in values:
            raise APIException(status_code=400, message="Unsupported OAuth provider.")
        return values[provider]

    def _oauth_state(self, provider: str, current_user: User) -> str:
        now = datetime.now(UTC)
        payload = {
            "purpose": "integration_oauth",
            "provider": provider,
            "sub": current_user.id,
            "org": current_user.organization_id,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    def _decode_oauth_state(self, provider: str, state: str) -> tuple[str, str]:
        try:
            payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise APIException(status_code=400, message="OAuth state is invalid or expired.") from exc
        if payload.get("purpose") != "integration_oauth" or payload.get("provider") != provider:
            raise APIException(status_code=400, message="OAuth state is invalid.")
        user_id = payload.get("sub")
        organization_id = payload.get("org")
        if not isinstance(user_id, str) or not isinstance(organization_id, str):
            raise APIException(status_code=400, message="OAuth state is invalid.")
        return user_id, organization_id

    async def start_oauth(self, provider: str, current_user: User) -> dict:
        client_id, client_secret, redirect_uri, authorization_url = self._oauth_settings(provider)
        if not client_id or not client_secret or not redirect_uri:
            raise APIException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                message=f"{provider.title()} OAuth is not configured.",
            )
        scopes = {
            "google": "https://www.googleapis.com/auth/calendar",
            "hubspot": "oauth crm.objects.contacts.read crm.objects.contacts.write crm.objects.companies.read crm.objects.companies.write crm.objects.deals.read crm.objects.deals.write",
            "slack": "chat:write channels:read",
        }[provider]
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "state": self._oauth_state(provider, current_user),
        }
        if provider == "google":
            params.update({"access_type": "offline", "prompt": "consent"})
        from urllib.parse import urlencode

        return {
            "message": f"{provider.title()} authorization started.",
            "auth_url": f"{authorization_url}?{urlencode(params)}",
            "status": "pending",
        }

    async def complete_oauth(
        self, db: AsyncSession, provider: str, code: str, state: str
    ) -> str:
        user_id, organization_id = self._decode_oauth_state(provider, state)
        user = await db.get(User, user_id)
        if user is None or user.organization_id != organization_id or not user.is_active:
            raise APIException(status_code=403, message="OAuth user is unavailable.")
        client_id, client_secret, redirect_uri, _ = self._oauth_settings(provider)
        token_urls = {
            "google": "https://oauth2.googleapis.com/token",
            "hubspot": "https://api.hubapi.com/oauth/v3/token",
            "slack": "https://slack.com/api/oauth.v2.access",
        }
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(token_urls[provider], data=data)
                response.raise_for_status()
                token_data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise APIException(status_code=502, message=f"{provider.title()} OAuth exchange failed.") from exc
        if provider == "slack" and not token_data.get("ok"):
            raise APIException(status_code=502, message="Slack OAuth exchange failed.")
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise APIException(status_code=502, message=f"{provider.title()} returned no access token.")

        provider_key = "slack_oauth" if provider == "slack" else provider
        integration = await self.repository.get_by_provider(db, organization_id, provider_key)
        if integration is None:
            integration = await self.repository.create(
                db,
                data={
                    "organization_id": organization_id,
                    "name": {"google": "Google Calendar", "hubspot": "HubSpot Migration", "slack": "Slack Sync"}[provider],
                    "provider": provider_key,
                },
            )
        integration.is_connected = True
        integration.status = "authenticated"
        integration.access_token = self._encrypt_secret(access_token)
        refresh_token = token_data.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            integration.refresh_token = self._encrypt_secret(refresh_token)
        integration.external_id = str(
            token_data.get("hub_id")
            or token_data.get("team", {}).get("id")
            or token_data.get("user_id")
            or ""
        ) or None
        integration.last_error = None
        integration.last_synced = None
        await self.repository.commit(db)
        return provider

    async def connect_zapier(
        self, db: AsyncSession, payload: ZapierConnectPayload, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        if not payload.webhook_url:
            raise APIException(status_code=400, message="Webhook URL is required.")
        webhook_url = payload.webhook_url
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    webhook_url,
                    json={
                        "event": "connection.test",
                        "organization_id": org_id,
                        "message": "CRM successfully connected to Zapier",
                    },
                )
            if response.status_code not in [200, 201, 202]:
                raise APIException(
                    status_code=502, message=f"Zapier returned {response.status_code}"
                )
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
                        "status": "synced",
                        "webhook_url": self._encrypt_secret(webhook_url),
                        "credentials": creds,
                    },
                )
            else:
                integration.is_connected = True
                integration.status = "synced"
                integration.webhook_url = self._encrypt_secret(webhook_url)
                integration.credentials = creds
            await self.repository.commit(db)
            await db.refresh(integration)
            integration.last_synced = datetime.now(UTC)
            await self.repository.commit(db)
            return {"message": "Zapier connected successfully.", "status": "success"}
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=500, message="Failed to connect Zapier") from e

    async def test_zapier_connection(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "zapier")
        if integration is None:
            raise APIException(status_code=404, message="Zapier integration is not connected.")
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Zapier webhook URL is missing.")
        zapier_payload = {
            "event": "test.connection",
            "organization_id": org_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"message": "CRM Zapier integration test successful.", "status": "success"},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=zapier_payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Zapier test payload sent successfully.", "status": "success"}
        except Exception as e:
            integration.last_error = f"Zapier delivery failed: {type(e).__name__}"
            await self.repository.commit(db)
            raise APIException(
                status_code=500, message="Failed to send Zapier test payload"
            ) from e

    async def trigger_zapier_event(
        self, db: AsyncSession, payload: Any, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "zapier")
        if integration is None:
            raise APIException(status_code=404, message="Zapier integration is not connected.")
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Zapier webhook URL is missing.")
        webhook_payload = {
            "event": payload.event_name,
            "organization_id": org_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload.payload,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=webhook_payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Zapier event sent successfully.", "status": "success"}
        except Exception as e:
            integration.last_error = f"Zapier delivery failed: {type(e).__name__}"
            await self.repository.commit(db)
            raise APIException(status_code=500, message="Failed to send Zapier webhook") from e

    async def delete_zapier_integration(
        self, db: AsyncSession, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        try:
            res = await db.execute(
                select(Integration).where(
                    Integration.provider == "zapier",
                    Integration.organization_id == org_id,
                )
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
            return {
                "message": "Zapier integration disconnected and webhook removed.",
                "status": "success",
            }
        except APIException:
            raise
        except Exception:
            await db.rollback()
            raise

    # --- Mailchimp ---
    async def connect_mailchimp(
        self, db: AsyncSession, payload: MailchimpConnectPayload, current_user: User
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        url = f"https://{payload.server_prefix}.api.mailchimp.com/3.0/lists/{payload.audience_id}"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, auth=("anystring", payload.api_key))
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            raise APIException(status_code=502, message="Mailchimp credentials or audience are invalid.") from exc

        integration = await self.repository.get_by_provider(db, org_id, "mailchimp")
        encrypted_config = self._encrypt_secret(
            json.dumps(
                {
                    "api_key": payload.api_key,
                    "server_prefix": payload.server_prefix,
                    "audience_id": payload.audience_id,
                }
            )
        )
        if integration is None:
            integration = await self.repository.create(
                db,
                data={
                    "organization_id": org_id,
                    "name": "Mailchimp Campaigns",
                    "provider": "mailchimp",
                },
            )
        integration.credentials = encrypted_config
        integration.is_connected = True
        integration.status = "authenticated"
        integration.sync_enabled = True
        integration.last_synced = None
        integration.last_error = None
        await self.repository.commit(db)
        return {"message": "Mailchimp connected successfully.", "status": "success"}

    async def disconnect_mailchimp(self, db: AsyncSession, current_user: User) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "mailchimp")
        if integration is None:
            raise APIException(status_code=404, message="Mailchimp integration is not connected.")
        integration.credentials = None
        integration.is_connected = False
        integration.status = "disconnected"
        integration.sync_enabled = False
        integration.last_error = None
        await self.repository.commit(db)
        return {"message": "Mailchimp disconnected successfully.", "status": "success"}

    # --- HubSpot mapping ---
    async def get_hubspot_mapping(self) -> dict:
        return {
            "lead_to_contact": {
                "first_name": "firstname",
                "last_name": "lastname",
                "email": "email",
                "company": "company_name",
            }
        }

    async def update_hubspot_mapping(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="HUBSPOT_SYNC_NOT_IMPLEMENTED",
            message="HubSpot synchronization and custom mapping persistence are not implemented.",
        )

    # --- Slack ---
    async def get_slack_config(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "slack")
        if integration is None:
            return {
                "name": "Slack Connector",
                "is_connected": False,
                "webhook_url": None,
                "events": [],
                "last_synced": None,
            }
        events = []
        if integration.enabled_events:
            try:
                events = json.loads(integration.enabled_events)
            except Exception:
                events = []
        return {
            "name": integration.name,
            "is_connected": integration.is_connected,
                "webhook_url": None,
            "events": events,
            "last_synced": integration.last_synced.isoformat() if integration.last_synced else None,
        }

    async def connect_slack(
        self, db: AsyncSession, payload: SlackConnectRequest, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        if not payload.webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is required.")
        if not str(payload.webhook_url).startswith("https://hooks.slack.com/"):
            raise APIException(status_code=400, message="Invalid Slack webhook URL.")
        try:
            await self._verify_slack_webhook(str(payload.webhook_url))
            verified_at = datetime.now(UTC)
            integration = await self.repository.get_by_provider(db, org_id, "slack")
            if integration is None:
                integration = await self.repository.create(
                    db,
                    data={
                        "organization_id": org_id,
                        "name": "Slack Connector",
                        "provider": "slack",
                        "is_connected": True,
                        "webhook_url": self._encrypt_secret(str(payload.webhook_url)),
                        "status": "synced",
                        "enabled_events": json.dumps(SLACK_ENABLED_EVENTS),
                        "credentials": json.dumps({"channel": "incoming-webhook", "type": "slack"}),
                        "sync_enabled": True,
                        "last_synced": verified_at,
                        "last_error": None,
                    },
                )
            else:
                integration.is_connected = True
                integration.status = "synced"
                integration.webhook_url = self._encrypt_secret(str(payload.webhook_url))
                integration.enabled_events = json.dumps(SLACK_ENABLED_EVENTS)
                integration.credentials = json.dumps(
                    {"channel": "incoming-webhook", "type": "slack"}
                )
                integration.sync_enabled = True
                integration.last_synced = verified_at
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
            return {"message": "Slack connected successfully.", "status": "success"}
        except httpx.HTTPError as e:
            await db.rollback()
            raise APIException(
                status_code=502,
                message="Slack webhook verification failed",
            ) from e
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=500, message="Failed to connect Slack") from e

    async def _verify_slack_webhook(self, webhook_url: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                webhook_url,
                json={"text": "CRM Slack connection verified."},
                headers={"Content-Type": "application/json"},
            )
        response.raise_for_status()

    async def update_slack_events(
        self, db: AsyncSession, payload: SlackEventsUpdateRequest, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        valid_events = [e for e in payload.events if e in SLACK_ENABLED_EVENTS]
        integration.enabled_events = json.dumps(valid_events)
        integration.last_error = None
        await self.repository.commit(db)
        await db.refresh(integration)
        return {
            "message": "Slack enabled events updated.",
            "status": "success",
            "events": valid_events,
        }

    async def test_slack_connection(self, db: AsyncSession, current_user: User | None) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")
        slack_payload = {
            "text": " *Slack Integration Test*\n\nYour CRM has successfully connected to Slack.\n\n"
            f"Organization : {org_id}\nTime : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {"message": "Slack test message sent successfully.", "status": "success"}
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned HTTP {e.response.status_code}"
            await self.repository.commit(db)
            raise APIException(
                status_code=e.response.status_code,
                message=f"Slack webhook returned HTTP {e.response.status_code}",
            ) from e
        except Exception as e:
            integration.last_error = f"Slack delivery failed: {type(e).__name__}"
            await self.repository.commit(db)
            raise APIException(
                status_code=500, message="Failed to send Slack test message"
            ) from e

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
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is not configured.")
        slack_payload = {"text": text}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned HTTP {e.response.status_code}"
            await self._commit_last_error(db)
            raise APIException(
                status_code=e.response.status_code,
                message=f"Slack webhook returned HTTP {e.response.status_code}",
            ) from e
        except Exception as e:
            integration.last_error = f"Slack delivery failed: {type(e).__name__}"
            await self._commit_last_error(db)
            raise APIException(
                status_code=500, message="Failed to send Slack event"
            ) from e

    async def _commit_last_error(self, db: AsyncSession) -> None:
        try:
            await self.repository.commit(db)
        except Exception:
            return

    async def trigger_slack_event(
        self, db: AsyncSession, payload: SlackEventPayload, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")

        enabled_events = self._enabled_events(integration)
        if enabled_events and payload.event_name not in enabled_events:
            raise APIException(
                status_code=400, message=f"Slack event '{payload.event_name}' is disabled."
            )

        await self._post_to_slack(
            db, integration, self._build_slack_text(payload.event_name, payload.data)
        )
        return {
            "message": f"Slack event '{payload.event_name}' sent successfully.",
            "status": "success",
        }

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
            logger.warning(
                "Slack auto-notification for event '%s' (org %s) failed: %s", event_name, org_id, e
            )

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
            raise APIException(
                status_code=500, message="Failed to disconnect Slack"
            ) from e

    async def send_slack_notification(
        self, db: AsyncSession, payload: SlackNotifyPayload, current_user: User | None
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_connected_by_provider(db, org_id, "slack")
        if integration is None:
            raise APIException(status_code=404, message="Slack integration is not connected.")
        webhook_url = self._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise APIException(status_code=400, message="Slack webhook URL is missing.")
        channel = payload.channel or "general"
        message = payload.message or "Notification from Enterprise CRM"
        slack_payload = {"text": f" *CRM Notification*\n\nChannel : #{channel}\n\n{message}"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
            integration.last_synced = datetime.utcnow()
            integration.last_error = None
            await self.repository.commit(db)
            return {
                "message": f"Slack notification posted successfully to #{channel}.",
                "status": "success",
            }
        except httpx.HTTPStatusError as e:
            integration.last_error = f"Slack returned HTTP {e.response.status_code}"
            await self.repository.commit(db)
            raise APIException(
                status_code=e.response.status_code,
                message=f"Slack webhook returned HTTP {e.response.status_code}",
            ) from e
        except Exception as e:
            integration.last_error = f"Slack delivery failed: {type(e).__name__}"
            await self.repository.commit(db)
            raise APIException(
                status_code=500, message="Failed to send Slack notification"
            ) from e

    # --- OAuth / misc ---

    async def google_oauth_callback(self) -> dict:
        raise APIException(status_code=501, message="Use the signed Google OAuth callback.")

    async def microsoft_oauth_callback(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="MICROSOFT_OAUTH_NOT_IMPLEMENTED",
            message="Microsoft OAuth is not implemented.",
        )

    async def get_sync_logs(self) -> list[dict]:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="INTEGRATION_SYNC_NOT_IMPLEMENTED",
            message="Synchronization logs are unavailable because provider sync is not implemented.",
        )

    async def retry_failed_sync(self, job_id: str | None, payload_job_id: str | None) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="INTEGRATION_SYNC_NOT_IMPLEMENTED",
            message="Synchronization retry is unavailable because provider sync is not implemented.",
        )

    async def save_custom_provider_key(
        self, provider_name: str | None, payload_provider_name: str | None
    ) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="CUSTOM_PROVIDER_NOT_IMPLEMENTED",
            message="Custom provider credential storage is not implemented.",
        )

    # --- Generic by-name operations ---
    async def get_integration_status(
        self, db: AsyncSession, name: str, current_user: User
    ) -> dict:
        org_id = await self.repository.resolve_org_id(db, current_user)
        i = await self.repository.get_by_name_like(db, org_id, name)
        if i:
            return self._status_dict(i)
        return {
            "name": name.capitalize(),
            "is_connected": False,
            "connection_status": "disconnected",
            "sync_status": "not_synced",
            "last_synced": None,
            "last_error": None,
        }

    async def connect_integration(
        self, db: AsyncSession, name: str, current_user: User | None
    ) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message=f"Provider-specific connection is not implemented for '{name}'.",
        )

    async def disconnect_integration(
        self, db: AsyncSession, name: str, current_user: User
    ) -> dict:
        provider = {"google-calendar": "google", "hubspot": "hubspot", "slack-sync": "slack_oauth"}.get(name)
        if provider is None:
            raise APIException(status_code=400, message=f"Unsupported integration '{name}'.")
        org_id = await self.repository.resolve_org_id(db, current_user)
        integration = await self.repository.get_by_provider(db, org_id, provider)
        if integration is None:
            raise APIException(status_code=404, message="Integration is not connected.")
        integration.is_connected = False
        integration.status = "disconnected"
        integration.access_token = None
        integration.refresh_token = None
        integration.external_id = None
        integration.sync_enabled = False
        integration.last_error = None
        await self.repository.commit(db)
        return {"message": f"{name} disconnected successfully.", "status": "success"}

    async def sync_integration(self, name: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            message=f"Synchronization is not implemented for '{name}'.",
        )


integration_service = IntegrationService()
