from types import SimpleNamespace

import httpx
import pytest

from app.workers.tasks import _deliver_one_integration_event


class _Result:
    def __init__(self, row=None, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def first(self):
        return self.row


class _Session:
    def __init__(self, *, result=None, integration=None):
        self.result = result or _Result()
        self.integration = integration
        self.executed = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, statement):
        self.executed.append(statement)
        return self.result

    async def get(self, model, entity_id):
        return self.integration

    async def commit(self):
        self.commits += 1


def _factory(*sessions):
    pending = list(sessions)
    return lambda: pending.pop(0)


def _integration(**overrides):
    values = {
        "id": "integration-1",
        "organization_id": "org-1",
        "is_connected": True,
        "webhook_url": "https://hooks.example.test/event",
        "status": "syncing",
        "last_synced": None,
        "last_error": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_integration_delivery_success_uses_stable_provider_idempotency_key(monkeypatch):
    claim = _Session(
        result=_Result(("org-1", "integration-1", "zapier", {"event": "x"}, 0))
    )
    integration = _integration()
    lookup = _Session(integration=integration)
    finalize = _Session(result=_Result(), integration=integration)
    captured = {}

    class _Response:
        status_code = 202

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, json, headers):
            captured.update(url=url, payload=json, headers=headers)
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: _Client())

    result = await _deliver_one_integration_event(
        _factory(claim, lookup, finalize), "delivery-1"
    )

    assert result == "delivered"
    assert captured["headers"] == {"Idempotency-Key": "delivery-1"}
    assert integration.status == "synced"
    assert integration.last_synced is not None
    assert finalize.commits == 1
    finalize_params = finalize.executed[0].compile().params
    assert "Delivered" in finalize_params.values()
    assert 1 in finalize_params.values()


@pytest.mark.asyncio
async def test_integration_delivery_failure_is_retried_without_false_success(monkeypatch):
    claim = _Session(
        result=_Result(("org-1", "integration-1", "slack", {"text": "x"}, 0))
    )
    integration = _integration()
    lookup = _Session(integration=integration)
    release = _Session(result=_Result(), integration=integration)

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, json, headers):
            raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: _Client())

    result = await _deliver_one_integration_event(
        _factory(claim, lookup, release), "delivery-1"
    )

    assert result == "failed"
    assert integration.status == "syncing"
    assert integration.last_error == "slack delivery failed: ConnectError"
    release_params = release.executed[0].compile().params
    assert "Retry" in release_params.values()
    assert 1 in release_params.values()


@pytest.mark.asyncio
async def test_expired_processing_delivery_can_be_reclaimed():
    claim = _Session(result=_Result())

    result = await _deliver_one_integration_event(_factory(claim), "delivery-1")

    assert result == "skipped"
    params = claim.executed[0].compile().params.values()
    assert "Processing" in params
    assert claim.commits == 1


@pytest.mark.asyncio
async def test_provider_success_does_not_overwrite_state_after_claim_is_lost(monkeypatch):
    claim = _Session(
        result=_Result(("org-1", "integration-1", "zapier", {"event": "x"}, 0))
    )
    integration = _integration()
    lookup = _Session(integration=integration)
    finalize = _Session(result=_Result(rowcount=0), integration=integration)

    class _Response:
        status_code = 202

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, json, headers):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: _Client())

    result = await _deliver_one_integration_event(
        _factory(claim, lookup, finalize), "delivery-1"
    )

    assert result == "lost_claim"
    assert integration.status == "syncing"
    assert integration.last_synced is None
