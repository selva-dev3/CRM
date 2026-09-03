from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import CallLog, User
from app.repositories.call_repository import CallRepository
from app.schemas.crm_schemas import CallLogBase
from app.services.call_service import CallService


def _make_call(**overrides) -> CallLog:
    defaults = {
        "id": "call-1",
        "organization_id": "org-1",
        "contact_id": "c-101",
        "call_type": "Outbound",
        "duration_seconds": 120,
        "notes": "Discussed pricing",
        "timestamp": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return CallLog(**defaults)


def _service_with(repo: CallRepository) -> CallService:
    return CallService(repository=repo)


def _user() -> User:
    return User(id="user-1", email="user@crm.com", organization_id="org-1")


@pytest.fixture(autouse=True)
def _stub_organization_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.services.call_service.organization_service.resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )


@pytest.mark.asyncio
async def test_get_call_raises_not_found_when_missing():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_call(db, "missing-call", _user())
    repo.get_by_id.assert_awaited_once_with(db, "missing-call", "org-1")


@pytest.mark.asyncio
async def test_log_call_resolves_org_and_serializes(monkeypatch):
    call = _make_call()
    repo: Any = CallRepository()
    repo.create = AsyncMock(return_value=call)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.call_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = CallLogBase(call_type="Inbound", duration_seconds=90, notes="Call back")
    result = await service.log_call(db, payload, _user())

    assert result["id"] == "call-1"
    assert result["call_type"] == "Outbound"
    assert result["notes"] == "Discussed pricing"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_outbound_returns_initiating_status():
    service = _service_with(CallRepository())
    result = await service.trigger_outbound("+1234567890", "c-101")

    assert result["status"] == "initiating"
    assert result["to"] == "+1234567890"
    assert result["call_sid"].startswith("CA")


@pytest.mark.asyncio
async def test_get_sentiment_requires_existing_call():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_sentiment(db, "missing-call", _user())
