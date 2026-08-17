from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.crm_schemas import (
    SlackConnectRequest,
    SlackEventPayload,
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
async def test_list_integrations_falls_back_to_defaults():
    repo = IntegrationRepository()
    repo.list_all = AsyncMock(return_value=[])
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_integrations(db)

    assert len(result) == len(DEFAULT_CONNECTORS)
    assert result[0]["name"] == "Slack Sync"


@pytest.mark.asyncio
async def test_connect_zapier_creates_integration(monkeypatch):
    integration = _make_integration(name="Zapier Connector", provider="zapier")
    repo = IntegrationRepository()
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

    data = repo.create.await_args.kwargs["data"]
    assert data["provider"] == "zapier"
    assert data["webhook_url"] == "https://hooks.zapier.com/abc"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_connect_zapier_requires_webhook():
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    payload = ZapierConnectPayload(webhook_url="")

    with pytest.raises(APIException):
        await service.connect_zapier(db, payload, None)


@pytest.mark.asyncio
async def test_get_slack_config_returns_default_when_missing():
    repo = IntegrationRepository()
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
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    service.notify_slack_event = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.connect_slack(db, SlackConnectRequest(webhook_url="https://hooks.slack.com/yyy"), None)

    data = repo.create.await_args.kwargs["data"]
    assert data["provider"] == "slack"
    assert data["enabled_events"].startswith("[")
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_connect_slack_fires_integration_connected():
    integration = _make_integration()
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    notify = AsyncMock()
    service.notify_slack_event = notify
    await service.connect_slack(db, SlackConnectRequest(webhook_url="https://hooks.slack.com/yyy"), None)

    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event_name"] == "integration.connected"
    assert notify.await_args.kwargs["org_id"] == "org-1"


@pytest.mark.asyncio
async def test_test_slack_connection_not_connected():
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.test_slack_connection(db, None)


@pytest.mark.asyncio
async def test_disconnect_slack(monkeypatch):
    integration = _make_integration()
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    service.notify_slack_event = AsyncMock()
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
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    notify = AsyncMock()
    service.notify_slack_event = notify
    result = await service.disconnect_slack(db, None)

    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event_name"] == "integration.disconnected"
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
    repo = IntegrationRepository()
    repo.get_by_name_like = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_integration_status(db, "stripe")

    assert result["name"] == "Stripe"
    assert result["is_connected"] is True


@pytest.mark.asyncio
async def test_connect_integration_creates_missing(monkeypatch):
    repo = IntegrationRepository()
    repo.get_by_name_like = AsyncMock(return_value=None)
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.create = AsyncMock(return_value=_make_integration())
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.connect_integration(db, "stripe", None)

    data = repo.create.await_args.kwargs["data"]
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
    repo = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=None)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fail_post(*args, **kwargs):
        raise AssertionError("_post_to_slack should not be called when Slack is disconnected")

    service._post_to_slack = fail_post
    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")


@pytest.mark.asyncio
async def test_notify_slack_event_skips_disabled_event():
    integration = _make_integration(enabled_events='["lead.updated"]')
    repo = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    service._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")

    service._post_to_slack.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_slack_event_posts_enabled_event():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    service._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.notify_slack_event(
        db, event_name="lead.created", data={"title": "Acme Corp"}, org_id="org-1"
    )

    service._post_to_slack.assert_awaited_once()
    text = service._post_to_slack.await_args.args[2]
    assert "lead.created" in text
    assert "Acme Corp" in text


@pytest.mark.asyncio
async def test_notify_slack_event_swallows_post_failure():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo = IntegrationRepository()
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def boom(*args, **kwargs):
        raise RuntimeError("webhook down")

    service._post_to_slack = boom
    await service.notify_slack_event(db, event_name="lead.created", data={}, org_id="org-1")


@pytest.mark.asyncio
async def test_trigger_slack_event_posts_successfully():
    integration = _make_integration(enabled_events='["lead.created"]')
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    service._post_to_slack = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    result = await service.trigger_slack_event(
        db, SlackEventPayload(event_name="lead.created", data={"title": "Acme"}), None
    )

    assert result["status"] == "success"
    service._post_to_slack.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_slack_event_raises_on_disabled_event():
    integration = _make_integration(enabled_events='["lead.updated"]')
    repo = IntegrationRepository()
    repo.resolve_org_id = AsyncMock(return_value="org-1")
    repo.get_connected_by_provider = AsyncMock(return_value=integration)
    service = IntegrationService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.trigger_slack_event(
            db, SlackEventPayload(event_name="lead.created", data={}), None
        )
