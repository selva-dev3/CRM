import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import Request

from app.api.v1.routers import whatsapp as router
from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
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
    ingest = AsyncMock(return_value=1)
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
