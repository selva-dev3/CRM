from typing import Any, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.crm_schemas import (
    SlackConnectRequest,
    SlackEventPayload,
    SlackEventsUpdateRequest,
    ZapierConnectPayload,
)
from app.services.integration_service import (
    DEFAULT_CONNECTORS,
    SLACK_ENABLED_EVENTS,
    IntegrationService,
)


def _make_integration(**overrides) -> Integration:
    defaults = {
        "id": "int-1",
        "organization_id": "org-1",
        "name": "Slack Connector",
        "provider": "slack",
        "is_connected": True,
        "status": "connected",
        "webhook_url": "https://hooks.slack.com/xxx",
        "credentials": None,
        "enabled_events": None,
        "sync_enabled": True,
        "last_synced": None,
        "last_error": None,
    }
    defaults.update(overrides)
    return Integration(**defaults)


@pytest.mark.asyncio
async def test_list_integrations_falls_back_to_disconnected_defaults():
    repo: Any = IntegrationRepository()
    repo.list_all = AsyncMock(return_value=[])
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_integrations(db)

    assert len(result) == len(DEFAULT_CONNECTORS)
    assert result[0]["name"] == "Slack Sync"
    assert result[0]["is_connected"] is False


@pytest.mark.asyncio
async def test_list_integrations_returns_empty_on_exception():
    repo: Any = IntegrationRepository()
    repo.list_all = AsyncMock(side_effect=RuntimeError("db down"))
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_integrations(db)

    assert result == []


@pytest.mark.asyncio
async def test_connect_zapier_creates_integration(monkeypatch):
    integration = _make_integration(name="Zapier Connector", provider="zapier")
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    payload = ZapierConnectPayload(webhook_url="https://hooks.zapier.com/abc")

    async def fake_post(self, url, json=None, headers=None):
        return type("R", (), {"status_code": 200})()

    monkeypatch.setattr("app.services.integration_service.httpx.AsyncClient.post", fake_post)

    result = await service.connect_zapier(db, payload, None)

    data = repo.create.await_args_list[-1].kwargs["data"]
    assert data["provider"] == "zapier"
    assert data["webhook_url"] == "https://hooks.zapier.com/abc"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_connect_zapier_requires_webhook():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    payload = ZapierConnectPayload(webhook_url="")

    with pytest.raises(APIException):
        await service.connect_zapier(db, payload, None)


@pytest.mark.asyncio
async def test_get_slack_config_returns_default_when_missing():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_slack_config(db, None)

    assert result["is_connected"] is False
    assert result["events"] == []


@pytest.mark.asyncio
async def test_connect_slack_creates_integration():
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service).notify_slack_event = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.connect_slack(
        db, SlackConnectRequest(webhook_url="https://hooks.slack.com/yyy"), None
    )

    data = repo.create.await_args_list[-1].kwargs["data"]
    assert data["provider"] == "slack"
    assert data["enabled_events"].startswith("[")
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_connect_slack_fires_integration_connected():
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    notify = AsyncMock()
    cast(Any, service).notify_slack_event = notify
    await service.connect_slack(
        db, SlackConnectRequest(webhook_url="https://hooks.slack.com/yyy"), None
    )

    notify.assert_awaited_once()
    assert notify.await_args_list[-1].kwargs["event_name"] == "integration.connected"
    assert notify.await_args_list[-1].kwargs["org_id"] == "org-1"


@pytest.mark.asyncio
async def test_test_slack_connection_not_connected():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.test_slack_connection(db, None)


@pytest.mark.asyncio
async def test_disconnect_slack(monkeypatch):
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service).notify_slack_event = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.disconnect_slack(db, None)

    assert integration.is_connected is False
    assert integration.status == "disconnected"
    assert integration.webhook_url is None
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_slack_fires_integration_disconnected():
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    notify = AsyncMock()
    cast(Any, service).notify_slack_event = notify
    result = await service.disconnect_slack(db, None)

    notify.assert_awaited_once()
    assert notify.await_args_list[-1].kwargs["event_name"] == "integration.disconnected"
    assert integration.webhook_url is None
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_handle_stripe_webhook_default():
    service = IntegrationService()
    result = await service.handle_stripe_webhook(None, None)
    assert "payment_intent.succeeded" in result["message"]


def test_default_connectors_and_events():
    assert len(DEFAULT_CONNECTORS) == 6
    assert "lead.created" in SLACK_ENABLED_EVENTS
    assert "integration.disconnected" in SLACK_ENABLED_EVENTS


@pytest.mark.asyncio
async def test_retry_failed_sync():
    service = IntegrationService()
    result = await service.retry_failed_sync("job-x", None)
    assert "job-x" in result["message"]


@pytest.mark.asyncio
async def test_get_integration_status_fallback():
    repo: Any = IntegrationRepository()
    repo.get_by_name_like = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_integration_status(db, "stripe")

    assert result["name"] == "Stripe"
    assert result["is_connected"] is False


@pytest.mark.asyncio
async def test_connect_integration_creates_missing(monkeypatch):
    repo: Any = IntegrationRepository()
    repo.get_by_name_like = AsyncMock(return_value=None)
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.create = AsyncMock(return_value=_make_integration())
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.connect_integration(db, "stripe", None)

    data = repo.create.await_args_list[-1].kwargs["data"]
    assert data["name"] == "Stripe"
    assert result["status"] == "success"
    assert "oauth2" in result["auth_url"]


@pytest.mark.asyncio
async def test_sync_integration():
    service = IntegrationService()
    result = await service.sync_integration("stripe")
    assert "stripe" in result["message"]


@pytest.mark.asyncio
async def test_notify_slack_event_skips_when_not_connected():
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fail_post(*args, **kwargs):
        raise AssertionError("_post_to_slack should not be called when Slack is disconnected")

    cast(Any, service)._post_to_slack = fail_post
    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")


@pytest.mark.asyncio
async def test_notify_slack_event_skips_disabled_event():
    integration = _make_integration(enabled_events='["lead.updated"]')
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")

    cast(Any, service)._post_to_slack.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_slack_event_posts_enabled_event():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(
        db, event_name="lead.created", data={"title": "Acme Corp"}, org_id="org-1"
    )

    cast(Any, service)._post_to_slack.assert_awaited_once()
    text = cast(Any, service)._post_to_slack.await_args_list[-1].args[2]
    assert "New lead created" in text
    assert "Acme Corp" in text


@pytest.mark.asyncio
async def test_notify_slack_event_swallows_post_failure():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def boom(*args, **kwargs):
        raise RuntimeError("webhook down")

    cast(Any, service)._post_to_slack = boom
    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")


@pytest.mark.asyncio
async def test_trigger_slack_event_posts_successfully():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.trigger_slack_event(
        db, SlackEventPayload(event_name="lead.created", data={"title": "Acme"}), None
    )

    assert result["status"] == "success"
    cast(Any, service)._post_to_slack.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_slack_event_raises_on_disabled_event():
    integration = _make_integration(enabled_events='["lead.updated"]')
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.trigger_slack_event(
            db, SlackEventPayload(event_name="lead.created", data={}), None
        )


@pytest.mark.asyncio
async def test_connect_slack_reconnects_updates_existing_integration():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    repo.create = AsyncMock()
    service = IntegrationService(repository=repo)
    cast(Any, service).notify_slack_event = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.connect_slack(
        db, SlackConnectRequest(webhook_url="https://hooks.slack.com/services/T/B/new"), None
    )

    assert result["status"] == "success"
    assert integration.webhook_url == "https://hooks.slack.com/services/T/B/new"
    assert integration.is_connected is True
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_slack_rejects_non_slack_webhook_url():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc:
        await service.connect_slack(
            db, SlackConnectRequest(webhook_url="https://example.com/not-slack"), None
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_connect_slack_requires_webhook_url():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc:
        await service.connect_slack(db, SlackConnectRequest(webhook_url=""), None)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_notify_slack_event_wrong_org_does_not_post():
    other_org_integration = _make_integration(enabled_events='["lead.created"]')
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-B")

    repo.get_connected_by_provider.assert_awaited_once_with(db, "org-B", "slack")
    cast(Any, service)._post_to_slack.assert_not_awaited()
    assert other_org_integration.webhook_url is not None


@pytest.mark.asyncio
async def test_notify_slack_event_skips_when_webhook_url_missing():
    integration = _make_integration(webhook_url=None)
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")

    cast(Any, service)._post_to_slack.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_slack_event_allows_event_when_enabled_events_empty():
    integration = _make_integration(enabled_events=None)
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")

    cast(Any, service)._post_to_slack.assert_awaited_once()


@pytest.mark.asyncio
async def test_notify_slack_event_allows_event_when_enabled_events_malformed():
    integration = _make_integration(enabled_events="not-json{{")
    repo: Any = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    cast(Any, service)._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")

    cast(Any, service)._post_to_slack.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_to_slack_http_error_sets_last_error_and_raises(monkeypatch):
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()

    request = httpx.Request("POST", "https://hooks.slack.com/services/x")
    response = httpx.Response(404, text="invalid_payload", request=request)

    async def fake_post(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "Slack 404",
            request=request,
            response=response,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(APIException):
        await service._post_to_slack(db, integration, "hello")

    assert integration.last_error is not None
    assert "404" in integration.last_error


@pytest.mark.asyncio
async def test_post_to_slack_generic_error_sets_last_error_and_raises(monkeypatch):
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()

    async def fake_post(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(APIException):
        await service._post_to_slack(db, integration, "hello")

    assert integration.last_error is not None
    assert "timed out" in integration.last_error


@pytest.mark.asyncio
async def test_update_slack_events_persists_enabled_events():
    integration = _make_integration()
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_slack_events(
        db,
        SlackEventsUpdateRequest(events=["lead.created", "deal.won", "not-a-real-event"]),
        None,
    )

    import json

    assert integration.enabled_events is not None
    parsed = json.loads(integration.enabled_events)
    assert "lead.created" in parsed
    assert "deal.won" in parsed
    assert "not-a-real-event" not in parsed
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_update_slack_events_raises_when_not_connected():
    repo: Any = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.update_slack_events(
            db, SlackEventsUpdateRequest(events=["lead.created"]), None
        )
