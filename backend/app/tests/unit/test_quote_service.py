from unittest.mock import AsyncMock

import pytest

from app.core.errors import NotFoundError
from app.models import User
from app.models.deal import Deal
from app.repositories.quote_repository import QuoteRepository
from app.schemas.crm_schemas import QuoteBase
from app.services.quote_service import QuoteService


def make_user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="rep@example.com",
        name="Rep",
        role="Sales Executive",
        is_active=True,
    )


def make_deal(**overrides) -> Deal:
    data = {
        "id": "deal-1",
        "organization_id": "org-1",
        "title": "Acme",
        "amount": 1000.0,
        "stage": "Proposal",
        "probability": 60.0,
        "assigned_to": "user-1",
    }
    data.update(overrides)
    return Deal(**data)


@pytest.mark.asyncio
async def test_create_quote_scopes_deal_and_persists_relationship(monkeypatch):
    repository = QuoteRepository()
    repository.get_deal_scoped = AsyncMock(return_value=make_deal())
    from app.models.quote import Quote

    repository.create = AsyncMock(
        return_value=Quote(
            id="quote-1",
            deal_id="deal-1",
            organization_id="org-1",
            quote_number="Q-1",
            total_amount=1000,
            status="Draft",
        )
    )
    db = AsyncMock()
    service = QuoteService(repository=repository)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    result = await service.create_quote(
        db,
        payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
        current_user=make_user(),
    )

    repository.get_deal_scoped.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )
    repository.create.assert_awaited_once()
    assert repository.create.await_args.kwargs["data"]["deal_id"] == "deal-1"
    assert result["deal_id"] == "deal-1"


@pytest.mark.asyncio
async def test_create_quote_returns_not_found_for_cross_tenant_deal(monkeypatch):
    repository = QuoteRepository()
    repository.get_deal_scoped = AsyncMock(return_value=None)
    service = QuoteService(repository=repository)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(NotFoundError):
        await service.create_quote(
            AsyncMock(),
            payload=QuoteBase(deal_id="other-deal", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )


@pytest.mark.asyncio
async def test_create_quote_rejects_invalid_status(monkeypatch):
    repository = QuoteRepository()
    repository.get_deal_scoped = AsyncMock(return_value=make_deal())
    repository.create = AsyncMock()
    service = QuoteService(repository=repository)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    from app.core.errors import APIException

    with pytest.raises(APIException) as exc_info:
        await service.create_quote(
            AsyncMock(),
            payload=QuoteBase(
                deal_id="deal-1", quote_number="Q-1", total_amount=1000, status="Unknown"
            ),
            current_user=make_user(),
        )
    assert exc_info.value.code == "INVALID_QUOTE_STATUS"
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_quote_rolls_back_when_commit_fails(monkeypatch):
    from app.models.quote import Quote

    repository = QuoteRepository()
    repository.get_deal_scoped = AsyncMock(return_value=make_deal())
    repository.create = AsyncMock(
        return_value=Quote(
            id="quote-1",
            deal_id="deal-1",
            organization_id="org-1",
            quote_number="Q-1",
            total_amount=1000,
            status="Draft",
        )
    )
    db = AsyncMock()
    db.commit.side_effect = RuntimeError("database unavailable")
    service = QuoteService(repository=repository)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    from app.core.errors import APIException

    with pytest.raises(APIException):
        await service.create_quote(
            db,
            payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )
    db.rollback.assert_awaited_once()
