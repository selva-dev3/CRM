from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.models.quote import Quote
from app.repositories.deal_repository import DealRepository
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


def make_quote(**overrides) -> Quote:
    data = {
        "id": "quote-1",
        "deal_id": "deal-1",
        "organization_id": "org-1",
        "quote_number": "Q-1",
        "total_amount": 1000.0,
        "status": "Draft",
    }
    data.update(overrides)
    return Quote(**data)


def make_service(
    *, quote: Quote | None = None, deal: Deal | None = None
) -> tuple[QuoteService, Any, Any]:
    quote_repository: Any = QuoteRepository()
    quote_repository.get_scoped = AsyncMock(return_value=quote)
    deal_repository: Any = DealRepository()
    deal_repository.get_by_id_scoped = AsyncMock(return_value=deal)
    return (
        QuoteService(
            repository=quote_repository,
            deal_repository=deal_repository,
        ),
        quote_repository,
        deal_repository,
    )


@pytest.mark.asyncio
async def test_create_quote_scopes_deal_and_persists_relationship(monkeypatch):
    service, repository, deal_repository = make_service(deal=make_deal())
    repository.create = AsyncMock(return_value=make_quote())
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    result = await service.create_quote(
        db,
        payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
        current_user=make_user(),
    )

    deal_repository.get_by_id_scoped.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )
    assert repository.create.await_args_list[-1].kwargs["data"]["deal_id"] == "deal-1"
    assert result["deal_id"] == "deal-1"


def test_create_quote_requires_deal_id_at_request_boundary():
    with pytest.raises(ValidationError):
        QuoteBase.model_validate({"quote_number": "Q-1", "total_amount": 1000, "status": "Draft"})


@pytest.mark.asyncio
async def test_create_quote_cross_tenant_deal_is_not_found(monkeypatch):
    service, repository, _ = make_service(deal=None)
    repository.create = AsyncMock()
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(NotFoundError):
        await service.create_quote(
            AsyncMock(spec=AsyncSession),
            payload=QuoteBase(deal_id="foreign-deal", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_quote_rejects_invalid_status(monkeypatch):
    service, repository, _ = make_service(deal=make_deal())
    repository.create = AsyncMock()
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(APIException) as exc_info:
        await service.create_quote(
            AsyncMock(spec=AsyncSession),
            payload=QuoteBase(
                deal_id="deal-1",
                quote_number="Q-1",
                total_amount=1000,
                status="Unknown",
            ),
            current_user=make_user(),
        )
    assert exc_info.value.code == "INVALID_QUOTE_STATUS"
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_quote_rolls_back_when_commit_fails(monkeypatch):
    service, repository, _ = make_service(deal=make_deal())
    repository.create = AsyncMock(return_value=make_quote())
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(APIException):
        await service.create_quote(
            db,
            payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_quotes_uses_scoped_repository():
    service, repository, _ = make_service()
    repository.list_scoped = AsyncMock(return_value=[make_quote()])
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_quotes(
        db,
        organization_id="org-1",
        page=1,
        limit=20,
        status="Draft",
        search="Q-1",
    )

    assert result[0]["id"] == "quote-1"
    repository.list_scoped.assert_awaited_once_with(
        db,
        organization_id="org-1",
        page=1,
        limit=20,
        status="Draft",
        search="Q-1",
    )


@pytest.mark.asyncio
async def test_get_quote_preserves_legacy_null_deal_id():
    service, _, _ = make_service(quote=make_quote(deal_id=None))

    result = await service.get_quote(
        AsyncMock(spec=AsyncSession), quote_id="quote-1", organization_id="org-1"
    )

    assert result["deal_id"] is None


@pytest.mark.asyncio
async def test_update_quote_scopes_quote_and_deal():
    quote = make_quote()
    service, repository, deal_repository = make_service(quote=quote, deal=make_deal())
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_quote(
        db,
        quote_id="quote-1",
        organization_id="org-1",
        payload=QuoteBase(deal_id="deal-1", quote_number="Q-2", total_amount=1200, status="Sent"),
    )

    repository.get_scoped.assert_awaited_once_with(db, quote_id="quote-1", organization_id="org-1")
    deal_repository.get_by_id_scoped.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )
    assert result["quote_number"] == "Q-2"
    assert quote.status == "Sent"


@pytest.mark.asyncio
async def test_update_quote_cross_tenant_deal_does_not_mutate():
    quote = make_quote()
    service, _, _ = make_service(quote=quote, deal=None)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.update_quote(
            db,
            quote_id="quote-1",
            organization_id="org-1",
            payload=QuoteBase(
                deal_id="foreign-deal",
                quote_number="Q-2",
                total_amount=1200,
                status="Sent",
            ),
        )

    assert quote.quote_number == "Q-1"
    assert quote.status == "Draft"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_quote_uses_scoped_delete():
    service, repository, _ = make_service()
    repository.delete_scoped = AsyncMock(return_value=True)
    db = AsyncMock(spec=AsyncSession)

    await service.delete_quote(db, quote_id="quote-1", organization_id="org-1")

    repository.delete_scoped.assert_awaited_once_with(
        db, quote_id="quote-1", organization_id="org-1"
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_quote_cross_tenant_is_not_found_and_not_committed():
    service, repository, _ = make_service()
    repository.delete_scoped = AsyncMock(return_value=False)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.delete_quote(db, quote_id="foreign-quote", organization_id="org-1")
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("affected", "ids", "expected"),
    [
        (2, ["quote-1", "quote-2"], 2),
        (1, ["quote-1", "foreign-quote"], 1),
        (0, ["foreign-quote"], 0),
        (0, ["unknown-quote"], 0),
    ],
)
async def test_bulk_delete_preserves_scoped_affected_count(affected, ids, expected):
    service, repository, _ = make_service()
    repository.bulk_delete_scoped = AsyncMock(return_value=affected)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_quotes(db, quote_ids=ids, organization_id="org-1")

    assert result["affected_count"] == expected
    repository.bulk_delete_scoped.assert_awaited_once_with(
        db, quote_ids=ids, organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_quote_actions_preserve_success_responses():
    service, _, _ = make_service(quote=make_quote())
    db = AsyncMock(spec=AsyncSession)

    sent = await service.send_quote(
        db,
        quote_id="quote-1",
        recipient_email="buyer@example.com",
        organization_id="org-1",
    )
    accepted = await service.accept_quote(db, quote_id="quote-1", organization_id="org-1")
    rejected = await service.reject_quote(
        db,
        quote_id="quote-1",
        reason="Budget constraints",
        organization_id="org-1",
    )
    pdf = await service.get_quote_pdf(db, quote_id="quote-1", organization_id="org-1")
    invoice = await service.convert_quote_to_invoice(
        db, quote_id="quote-1", organization_id="org-1"
    )
    revision = await service.create_quote_revision(db, quote_id="quote-1", organization_id="org-1")
    revisions = await service.get_quote_revisions(db, quote_id="quote-1", organization_id="org-1")

    assert sent["message"] == "Quote proposal sent to buyer@example.com"
    assert accepted["status"] == "success"
    assert rejected["message"].endswith("Budget constraints")
    assert pdf == {"pdf_url": "https://api.crm.com/quotes/quote-1.pdf"}
    assert invoice["invoice_number"] == "INV-Q-1"
    assert revision["quote_number"] == "Q-1-v2"
    assert len(revisions) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("send_quote", {"recipient_email": "buyer@example.com"}),
        ("accept_quote", {}),
        ("reject_quote", {"reason": "Budget constraints"}),
        ("get_quote_pdf", {}),
        ("convert_quote_to_invoice", {}),
        ("create_quote_revision", {}),
        ("get_quote_revisions", {}),
    ],
)
@pytest.mark.parametrize("quote_id", ["foreign-quote", "missing-quote"])
async def test_cross_tenant_and_missing_quote_actions_are_not_found_without_mutation(
    method_name, kwargs, quote_id
):
    service, repository, _ = make_service(quote=None)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await getattr(service, method_name)(
            db,
            quote_id=quote_id,
            organization_id="org-1",
            **kwargs,
        )

    repository.get_scoped.assert_awaited_once_with(db, quote_id=quote_id, organization_id="org-1")
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_quotes_for_deal_is_tenant_scoped():
    service, repository, _ = make_service()
    repository.list_by_deal = AsyncMock(return_value=[make_quote()])
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_quotes_for_deal(db, deal_id="deal-1", organization_id="org-1")

    assert result[0]["deal_id"] == "deal-1"
    repository.list_by_deal.assert_awaited_once_with(db, deal_id="deal-1", organization_id="org-1")
