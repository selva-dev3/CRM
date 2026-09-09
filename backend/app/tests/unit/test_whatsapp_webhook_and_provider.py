import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import Request

from app.api.v1.routers import whatsapp as router
from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError
from app.schemas.whatsapp import WebhookIngestResult
from app.services.whatsapp_provider_service import WhatsAppProviderService, matches_media_sha256
from app.services.whatsapp_service import WhatsAppService

TEST_APP_SECRET = "unit-test-app-secret"  # noqa: S105 - synthetic test credential
TEST_VERIFY_TOKEN = "unit-test-verify-token"  # noqa: S105 - synthetic test credential


def test_media_integrity_accepts_meta_base64_and_hex_encodings():
    content = b"verified media"
    digest = hashlib.sha256(content).digest()

    assert matches_media_sha256(content, digest.hex())
    assert matches_media_sha256(content, base64.b64encode(digest).decode())
    assert not matches_media_sha256(content + b"tampered", digest.hex())


def _request(body: bytes, signature: str | None) -> Request:
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    headers = [] if signature is None else [(b"x-hub-signature-256", signature.encode())]
    return Request(
        {"type": "http", "method": "POST", "path": "/webhook", "headers": headers}, receive
    )


@pytest.mark.asyncio
async def test_webhook_verification_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", TEST_VERIFY_TOKEN)
    rate_limit = AsyncMock()
    monkeypatch.setattr(router, "enforce_rate_limit", rate_limit)

    assert await router.verify_webhook("subscribe", TEST_VERIFY_TOKEN, "challenge") == "challenge"
    with pytest.raises(ForbiddenError):
        await router.verify_webhook("subscribe", "wrong-token", "challenge")


@pytest.mark.asyncio
async def test_webhook_signature_is_checked_before_persistence(monkeypatch):
    body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1001",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "2002"},
                                "messages": [
                                    {
                                        "id": "wamid.test",
                                        "from": "14155552671",
                                        "timestamp": "1788921000",
                                        "type": "text",
                                        "text": {"body": "Hi"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", TEST_APP_SECRET)
    rate_limit = AsyncMock()
    monkeypatch.setattr(router, "enforce_rate_limit", rate_limit)
    ingest = AsyncMock(return_value=WebhookIngestResult(inserted_messages=1, matched_changes=1))
    commit = AsyncMock()
    monkeypatch.setattr(router.service.repository, "ingest", ingest)
    monkeypatch.setattr(router.service, "commit", commit)
    db = AsyncMock()

    with pytest.raises(ForbiddenError):
        await router.receive_webhook(_request(body, None), db)
    ingest.assert_not_awaited()

    digest = hmac.new(TEST_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = await router.receive_webhook(_request(body, f"sha256={digest}"), db)

    assert response.status_code == 204
    rate_limit.assert_awaited_once_with("webhook", settings.WHATSAPP_WEBHOOK_RATE_PER_MINUTE)
    ingest.assert_awaited_once()
    commit.assert_awaited_once_with(db)


@pytest.mark.asyncio
async def test_provider_acceptance_returns_real_provider_id_without_delivery_claim(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        is_success = True

        @staticmethod
        def json():
            return {"messages": [{"id": "wamid.provider-confirmed"}]}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs)
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    provider = WhatsAppProviderService("synthetic-access-token", "v23.0")

    provider_id = await provider.send_text("2002", "+14155552671", "Hello", "message-1")

    assert provider_id == "wamid.provider-confirmed"
    assert captured["url"] == "https://graph.facebook.com/v23.0/2002/messages"
    assert captured["kwargs"]["json"]["biz_opaque_callback_data"] == "message-1"


@pytest.mark.asyncio
async def test_ambiguous_provider_failure_is_not_reported_as_sent(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("synthetic outage")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    provider = WhatsAppProviderService("synthetic-access-token", "v23.0")

    with pytest.raises(APIException) as exc_info:
        await provider.send_text("2002", "+14155552671", "Hello", "message-1")

    assert exc_info.value.code == "WHATSAPP_OUTCOME_UNKNOWN"


@pytest.mark.asyncio
async def test_provider_rate_limit_is_safe_to_retry_after_requested_delay(monkeypatch):
    class Response:
        status_code = 429
        is_success = False
        headers = {"retry-after": "90"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    provider = WhatsAppProviderService("synthetic-access-token", "v23.0")

    with pytest.raises(APIException) as exc_info:
        await provider.send_text("2002", "+14155552671", "Hello", "message-1")

    assert exc_info.value.code == "WHATSAPP_PROVIDER_RATE_LIMITED"
    assert exc_info.value.fields == {"retry_after_seconds": 90}


@pytest.mark.asyncio
async def test_connection_verification_requires_current_app_waba_subscription(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_APP_ID", "3003")
    monkeypatch.setattr(
        "app.services.whatsapp_service.enforce_rate_limit", AsyncMock()
    )
    service = WhatsAppService()
    user = SimpleNamespace(id="admin-a", organization_id="org-a", is_active=True)
    assignee = SimpleNamespace(id="agent-a", organization_id="org-a", is_active=True)
    config = SimpleNamespace(
        id="config-a",
        organization_id="org-a",
        business_account_id="1001",
        phone_number_id="2002",
        default_assignee_id="agent-a",
        ai_user_id=None,
        display_phone_number=None,
        verified_name=None,
        enabled=False,
    )
    client = MagicMock()
    client.request = AsyncMock(
        side_effect=[
            {
                "data": [
                    {
                        "id": "2002",
                        "display_phone_number": "+1 415-555-2671",
                        "verified_name": "Example Business",
                    }
                ]
            },
            {"data": [{"whatsapp_business_api_data": {"id": "another-app"}}]},
        ]
    )
    service.permissions = AsyncMock(
        side_effect=[{"integrations:manage"}, {"whatsapp:read_assigned"}]
    )
    service.repository.configuration = AsyncMock(return_value=config)
    service.repository.user = AsyncMock(return_value=assignee)
    service.provider = AsyncMock(return_value=client)

    with pytest.raises(ConflictError) as exc_info:
        await service.verify(AsyncMock(), user)

    assert exc_info.value.code == "WHATSAPP_WEBHOOK_NOT_SUBSCRIBED"
    assert config.enabled is False


@pytest.mark.asyncio
async def test_status_reports_runtime_readiness_without_exposing_full_phone(monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(settings, "AI_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr(
        "app.services.whatsapp_service.worker_heartbeat",
        AsyncMock(return_value=("HEALTHY", now)),
    )
    monkeypatch.setattr(
        "app.services.whatsapp_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["ai:generate", "whatsapp:send", "whatsapp:read_all"]),
    )
    service = WhatsAppService()
    current_user = SimpleNamespace(id="admin-a", organization_id="org-a", is_active=True)
    ai_user = SimpleNamespace(id="ai-a", organization_id="org-a", is_active=True)
    config = SimpleNamespace(
        organization_id="org-a",
        enabled=True,
        phone_index_ready=True,
        business_account_id="1001",
        phone_number_id="2002",
        display_phone_number="+1 415-555-2671",
        verified_name="Example Business",
        api_version="v23.0",
        default_phone_region="US",
        last_webhook_at=now,
        last_successful_message_at=None,
        ai_user_id="ai-a",
        default_assignee_id="agent-a",
    )
    catalog = SimpleNamespace(status="connected")
    service.permissions = AsyncMock(return_value={"integrations:read"})
    service.repository.configuration = AsyncMock(return_value=config)
    service.repository.catalog = AsyncMock(return_value=catalog)
    service.repository.user = AsyncMock(return_value=ai_user)
    service.repository.oldest_pending_at = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.ai_runtime_service.ai_runtime_service.configuration_readiness",
        AsyncMock(return_value="READY"),
    )

    result = await service.status(AsyncMock(), current_user)

    assert result.ready is True
    assert result.masked_phone_number == "••••2671"
    assert result.worker_status == "HEALTHY"
    assert result.webhook_status == "OBSERVED"
    assert result.ai_status == "READY"
    from datetime import timedelta

    service.repository.oldest_pending_at.return_value = now - timedelta(minutes=10)
    delayed = await service.status(AsyncMock(), current_user)
    assert delayed.ready is False
    assert delayed.backlog_age_seconds >= 600

    monkeypatch.setattr(
        "app.services.whatsapp_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["ai:generate", "whatsapp:send"]),
    )
    unauthorized = await service.status(AsyncMock(), current_user)
    assert unauthorized.ai_status == "PERMISSION_MISSING"


@pytest.mark.asyncio
async def test_manual_retry_allows_deterministic_failure_but_rejects_unknown_outcome(monkeypatch):
    from app.models.whatsapp import WhatsAppMessage
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    service = WhatsAppService()
    user = SimpleNamespace(id="agent-a", organization_id="org-a", is_active=True)
    conversation = SimpleNamespace(id="conversation-a")
    message = WhatsAppMessage(
        id="message-a",
        direction="OUTBOUND",
        status="FAILED",
        work_status="FAILED",
        error_code="WHATSAPP_PROVIDER_RATE_LIMITED",
        error_message="Provider rate limited the request.",
        attempts=3,
        next_attempt_at=None,
        claimed_at=datetime.now(UTC),
        failed_at=datetime.now(UTC),
    )
    config = SimpleNamespace(enabled=True)
    identity = SimpleNamespace(consent="UNKNOWN")
    service.conversation = AsyncMock(return_value=conversation)
    service.repository.message = AsyncMock(return_value=message)
    service.repository.configuration = AsyncMock(return_value=config)
    service.repository.identity = AsyncMock(return_value=identity)
    service.audit = MagicMock()
    service.commit = AsyncMock()

    result = await service.retry_failed_message(
        AsyncMock(), user, conversation.id, message.id
    )

    assert result is message
    assert message.status == "PENDING"
    assert message.work_status == "PENDING"
    assert message.attempts == 0
    assert message.error_code is None
    assert message.retryable is False

    message.status = "UNKNOWN"
    message.work_status = "FAILED"
    with pytest.raises(ConflictError) as exc_info:
        await service.retry_failed_message(AsyncMock(), user, conversation.id, message.id)
    assert exc_info.value.code == "WHATSAPP_UNKNOWN_RETRY_PROHIBITED"


@pytest.mark.asyncio
async def test_template_sync_fetches_all_pages_before_replacing_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    service = WhatsAppService()
    config = SimpleNamespace(
        id="config-a", organization_id="org-a", enabled=True, business_account_id="1001"
    )
    user = SimpleNamespace(id="user-a", organization_id="org-a", is_active=True)
    client = MagicMock()
    client.request = AsyncMock(
        side_effect=[
            {
                "data": [{"id": "template-1"}],
                "paging": {"cursors": {"after": "cursor-2"}, "next": "redacted"},
            },
            {"data": [{"id": "template-2"}]},
        ]
    )
    service.permissions = AsyncMock(return_value={"integrations:manage"})
    service.provider = AsyncMock(return_value=client)
    service.repository.configuration = AsyncMock(return_value=config)
    service.repository.replace_templates = AsyncMock()
    service.repository.templates = AsyncMock(return_value=[])
    service.audit = MagicMock()
    service.commit = AsyncMock()

    db = AsyncMock()
    assert await service.sync_templates(db, user) == []

    assert client.request.await_count == 2
    assert client.request.await_args_list[1].kwargs["params"]["after"] == "cursor-2"
    service.repository.replace_templates.assert_awaited_once_with(
        db,
        config,
        [{"id": "template-1"}, {"id": "template-2"}],
    )
