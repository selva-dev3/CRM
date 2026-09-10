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
from sqlalchemy.exc import IntegrityError

from app.api.v1.routers import whatsapp as router
from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError
from app.schemas.whatsapp import IntegrationWrite, WebhookIngestResult
from app.services.whatsapp_provider_service import WhatsAppProviderService, matches_media_sha256
from app.services.whatsapp_service import WhatsAppService

TEST_APP_SECRET = "unit-test-app-secret"  # noqa: S105 - synthetic test credential
TEST_VERIFY_TOKEN = "unit-test-verify-token"  # noqa: S105 - synthetic test credential


@pytest.fixture
def account_correction(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v25.0")
    monkeypatch.setattr("app.services.whatsapp_service.enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(
        "app.services.whatsapp_service.IntegrationService._encrypt_secret",
        lambda value: "enc:v1:synthetic",
    )
    service = WhatsAppService()
    config = SimpleNamespace(
        id="config-a",
        organization_id="org-a",
        business_account_id="1001",
        phone_number_id="2001",
        enabled=False,
        last_webhook_at=None,
        last_successful_message_at=None,
        display_phone_number="old-display",
        verified_name="old-name",
        phone_index_ready=True,
        phone_backfill_stage="done",
        phone_backfill_cursor="old-cursor",
        default_phone_region="IN",
        api_version="v25.0",
        default_assignee_id=None,
        ai_user_id=None,
        catalog_integration_id="catalog-a",
        updated_at=None,
    )
    service.permissions = AsyncMock(return_value={"integrations:manage"})
    service.repository.configuration = AsyncMock(return_value=config)
    service.repository.has_account_records = AsyncMock(return_value=False)
    service.repository.catalog = AsyncMock(
        return_value=SimpleNamespace(access_token="enc:v1:old", updated_at=None)  # noqa: S106
    )
    service.audit = MagicMock()
    service.status = AsyncMock(return_value="status-result")
    user = SimpleNamespace(id="admin-a", organization_id="org-a")
    payload = IntegrationWrite(
        business_account_id="1002",
        phone_number_id="2002",
        access_token="synthetic-token-for-unit-tests",  # noqa: S106 - synthetic test credential
        api_version="v25.0",
        default_phone_region="IN",
    )
    return service, config, user, payload


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_field", ["both", "business_account_id", "phone_number_id"])
async def test_unused_account_identity_can_be_corrected(account_correction, changed_field):
    service, config, user, payload = account_correction
    if changed_field != "both":
        other = (
            "phone_number_id" if changed_field == "business_account_id" else "business_account_id"
        )
        setattr(payload, other, getattr(config, other))
    db = AsyncMock()
    assert await service.configure(db, user, payload) == "status-result"
    assert config.business_account_id == payload.business_account_id
    assert config.phone_number_id == payload.phone_number_id
    assert config.display_phone_number is None
    assert config.verified_name is None
    assert config.phone_index_ready is False
    assert config.phone_backfill_stage == "contacts"
    assert config.phone_backfill_cursor is None
    assert config.enabled is False
    service.repository.configuration.assert_awaited_once_with(db, "org-a", lock=True)
    service.repository.has_account_records.assert_awaited_once_with(db, config)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocker", ["records", "enabled", "last_webhook_at", "last_successful_message_at"]
)
async def test_used_account_identity_cannot_be_corrected(account_correction, blocker):
    service, config, user, payload = account_correction
    if blocker == "records":
        service.repository.has_account_records.return_value = True
    else:
        setattr(config, blocker, True if blocker == "enabled" else datetime.now(UTC))
    db = AsyncMock()
    with pytest.raises(ConflictError):
        await service.configure(db, user, payload)
    assert config.business_account_id == "1001"
    assert config.phone_number_id == "2001"
    service.repository.catalog.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_account_can_refresh_credentials_with_history(account_correction):
    service, config, user, payload = account_correction
    payload.business_account_id = config.business_account_id
    payload.phone_number_id = config.phone_number_id
    service.repository.has_account_records.return_value = True
    db = AsyncMock()
    await service.configure(db, user, payload)
    service.repository.has_account_records.assert_not_awaited()
    assert config.phone_index_ready is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_account_correction_commit_failure_propagates(account_correction):
    service, _, user, payload = account_correction
    db = AsyncMock()
    db.commit.side_effect = RuntimeError("synthetic commit failure")
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        await service.configure(db, user, payload)
    db.rollback.assert_awaited_once()
    service.status.assert_not_awaited()


class _ConstraintError(Exception):
    def __init__(self, constraint_name):
        super().__init__(constraint_name)
        self.constraint_name = constraint_name


@pytest.mark.asyncio
async def test_phone_number_collision_is_reported_as_conflict(account_correction):
    service, _, user, payload = account_correction
    db = AsyncMock()
    db.commit.side_effect = IntegrityError(
        "update", {}, _ConstraintError(service.PHONE_NUMBER_UNIQUE_CONSTRAINT)
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.configure(db, user, payload)

    assert exc_info.value.code == "WHATSAPP_PHONE_ALREADY_CONNECTED"
    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_unexpected_integrity_error_is_not_hidden(account_correction):
    service, _, user, payload = account_correction
    db = AsyncMock()
    failure = IntegrityError("update", {}, _ConstraintError("unexpected_constraint"))
    db.commit.side_effect = failure

    with pytest.raises(IntegrityError) as exc_info:
        await service.configure(db, user, payload)

    assert exc_info.value is failure
    db.rollback.assert_awaited_once()


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
        api_version="v25.0",
        default_assignee_id="agent-a",
        ai_user_id=None,
        catalog_integration_id="catalog-a",
        updated_at=None,
        display_phone_number=None,
        verified_name=None,
        enabled=False,
    )
    catalog = SimpleNamespace(access_token="enc:v1:token", updated_at=None)  # noqa: S106
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
    service.repository.catalog = AsyncMock(return_value=catalog)
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
        id="config-a",
        organization_id="org-a",
        enabled=True,
        business_account_id="1001",
        phone_number_id="2002",
        api_version="v25.0",
        default_assignee_id="agent-a",
        ai_user_id=None,
        catalog_integration_id="catalog-a",
        updated_at=None,
    )
    catalog = SimpleNamespace(access_token="enc:v1:token", updated_at=None)  # noqa: S106
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
    service.repository.catalog = AsyncMock(return_value=catalog)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["verify", "sync_templates"])
async def test_provider_result_is_rejected_after_account_correction(monkeypatch, operation):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_APP_ID", "3003")
    monkeypatch.setattr("app.services.whatsapp_service.enforce_rate_limit", AsyncMock())
    service = WhatsAppService()
    original = SimpleNamespace(
        id="config-a",
        organization_id="org-a",
        business_account_id="1001",
        phone_number_id="2002",
        api_version="v25.0",
        enabled=True,
        default_assignee_id="agent-a",
        ai_user_id=None,
        catalog_integration_id="catalog-a",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    corrected = SimpleNamespace(**vars(original))
    corrected.business_account_id = "corrected-account"
    corrected.phone_number_id = "corrected-phone"
    corrected.enabled = False
    corrected.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    catalog = SimpleNamespace(access_token="enc:v1:token", updated_at=None)  # noqa: S106
    user = SimpleNamespace(id="admin-a", organization_id="org-a", is_active=True)
    assignee = SimpleNamespace(id="agent-a", organization_id="org-a", is_active=True)
    client = MagicMock()
    if operation == "verify":
        client.request = AsyncMock(
            side_effect=[
                {
                    "data": [
                        {
                            "id": "2002",
                            "display_phone_number": "+1 415-555-2671",
                            "verified_name": "Old Account",
                        }
                    ]
                },
                {"data": [{"id": "3003"}]},
            ]
        )
        service.repository.user = AsyncMock(return_value=assignee)
        service.permissions = AsyncMock(
            side_effect=[{"integrations:manage"}, {"whatsapp:read_assigned"}]
        )
    else:
        client.request = AsyncMock(return_value={"data": [{"id": "old-template"}]})
        service.permissions = AsyncMock(return_value={"integrations:manage"})
        service.repository.templates = AsyncMock(return_value=[])
    service.provider = AsyncMock(return_value=client)
    service.repository.configuration = AsyncMock(side_effect=[original, corrected])
    service.repository.catalog = AsyncMock(return_value=catalog)
    service.repository.replace_templates = AsyncMock()
    service.audit = MagicMock()
    service.commit = AsyncMock()
    db = AsyncMock()

    with pytest.raises(ConflictError) as exc_info:
        await getattr(service, operation)(db, user)

    assert exc_info.value.code == "WHATSAPP_CONFIGURATION_CHANGED"
    db.rollback.assert_awaited_once()
    service.repository.replace_templates.assert_not_awaited()
    service.commit.assert_not_awaited()
