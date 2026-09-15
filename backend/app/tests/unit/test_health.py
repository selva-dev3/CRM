from unittest.mock import AsyncMock

import pytest

from app import main


@pytest.mark.asyncio
async def test_liveness_does_not_probe_dependencies():
    response = await main.liveness()

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_all_dependencies_healthy(monkeypatch):
    monkeypatch.setattr(main, "_database_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(main, "_redis_ready", AsyncMock(return_value=True))

    response = await main.readiness()

    assert response.status_code == 200
    assert response.body == b'{"status":"ok","checks":{"database":"ok","redis":"ok"}}'


@pytest.mark.asyncio
async def test_readiness_returns_service_unavailable_when_dependency_is_down(monkeypatch):
    monkeypatch.setattr(main, "_database_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(main, "_redis_ready", AsyncMock(return_value=False))

    response = await main.readiness()

    assert response.status_code == 503
    assert response.body == (b'{"status":"error","checks":{"database":"ok","redis":"unavailable"}}')
