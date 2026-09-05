from types import SimpleNamespace
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
    quote_repository.list_items = AsyncMock(return_value=[])
    quote_repository.get_invoice_reference = AsyncMock(return_value=None)
    quote_repository.queue_delivery = AsyncMock()
    deal_repository: Any = DealRepository()
    deal_repository.get_by_id_scoped = AsyncMock(return_value=deal)
    deal_repository.get_sales_customer = AsyncMock(return_value=(None, None))
    return (
        QuoteService(
            repository=quote_repository,
            deal_repository=deal_repository,
        ),
        quote_repository,
        deal_repository,
    )


@pytest.mark.asyncio
async def test_approve_quote_queues_customer_delivery_in_same_transaction():
    quote = make_quote(currency="INR", delivery_status=None)
    service, repository, deal_repository = make_service(quote=quote, deal=make_deal())
    repository.lock_scoped = AsyncMock(return_value=quote)
    repository.approve = AsyncMock()
    repository.list_items = AsyncMock(
        return_value=[
            SimpleNamespace(
                quantity=1,
                unit_price=1000,
                discount_percent=0,
                tax_percent=0,
            )
        ]
    )
    contact = SimpleNamespace(id="contact-1", company_id="company-1", email="buyer@example.com")
    deal_repository.get_sales_customer = AsyncMock(
        return_value=(SimpleNamespace(id="company-1"), contact)
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.approve_quote(
        db, quote_id=quote.id, organization_id="org-1", actor_id="user-1"
    )

    repository.approve.assert_awaited_once()
    repository.queue_delivery.assert_awaited_once()
    assert repository.queue_delivery.await_args.kwargs["recipient_email"] == contact.email
    db.commit.assert_awaited_once()
    assert result["quote_number"] == "Q-1"


@pytest.mark.asyncio
async def test_repeated_quote_approval_does_not_duplicate_delivery():
    quote = make_quote(
        currency="INR",
        status="Approved",
        approved_at=SimpleNamespace(),
        delivery_status="Pending",
    )
    service, repository, deal_repository = make_service(quote=quote, deal=make_deal())
    repository.lock_scoped = AsyncMock(return_value=quote)
    repository.approve = AsyncMock()
    repository.list_items = AsyncMock(
        return_value=[
            SimpleNamespace(
                quantity=1,
                unit_price=1000,
                discount_percent=0,
                tax_percent=0,
            )
        ]
    )
    deal_repository.get_sales_customer = AsyncMock(
        return_value=(
            SimpleNamespace(id="company-1"),
            SimpleNamespace(id="contact-1", company_id="company-1", email="buyer@example.com"),
        )
    )

    await service.approve_quote(
        AsyncMock(spec=AsyncSession),
        quote_id=quote.id,
        organization_id="org-1",
        actor_id="user-1",
    )

    repository.approve.assert_not_awaited()
    repository.queue_delivery.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_quote_requires_closed_won_automation(monkeypatch):
    service, repository, deal_repository = make_service(deal=make_deal())
    repository.create = AsyncMock(return_value=make_quote())
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(APIException) as exc_info:
        await service.create_quote(
            db,
            payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )

    assert exc_info.value.code == "AUTOMATIC_QUOTE_REQUIRED"
    deal_repository.get_by_id_scoped.assert_not_awaited()
    repository.create.assert_not_awaited()


def test_create_quote_requires_deal_id_at_request_boundary():
    with pytest.raises(ValidationError):
        QuoteBase.model_validate({"quote_number": "Q-1", "total_amount": 1000, "status": "Draft"})


@pytest.mark.asyncio
async def test_create_quote_does_not_probe_cross_tenant_deal(monkeypatch):
    service, repository, _ = make_service(deal=None)
    repository.create = AsyncMock()
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(APIException) as exc_info:
        await service.create_quote(
            AsyncMock(spec=AsyncSession),
            payload=QuoteBase(deal_id="foreign-deal", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )
    assert exc_info.value.code == "AUTOMATIC_QUOTE_REQUIRED"
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
    assert exc_info.value.code == "AUTOMATIC_QUOTE_REQUIRED"
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_quote_never_starts_a_database_transaction(monkeypatch):
    service, repository, _ = make_service(deal=make_deal())
    repository.create = AsyncMock(return_value=make_quote())
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(service, "resolve_organization_id", AsyncMock(return_value="org-1"))

    with pytest.raises(APIException) as exc_info:
        await service.create_quote(
            db,
            payload=QuoteBase(deal_id="deal-1", quote_number="Q-1", total_amount=1000),
            current_user=make_user(),
        )
    assert exc_info.value.code == "AUTOMATIC_QUOTE_REQUIRED"
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_closed_won_quote_uses_org_sequence_and_snapshot_totals(monkeypatch):
    deal = make_deal(stage="Closed Won", company_id="company-1", contact_id="contact-1")
    service, repository, deal_repository = make_service(deal=deal)
    organization = SimpleNamespace(id="org-1", currency="INR", quote_prefix="QUO", quote_sequence=6)
    line = SimpleNamespace(
        product_id="product-1",
        product_name="CRM License",
        quantity=2,
        unit_price=500,
        discount_percent=10,
        tax_percent=18,
    )
    company = SimpleNamespace(id="company-1")
    contact = SimpleNamespace(id="contact-1", company_id="company-1")
    product = SimpleNamespace(id="product-1", name="Mutable Product Name")
    created_quote = make_quote(
        quote_number="QUO-2026-000007",
        total_amount=1062,
        automatic_deal_id="deal-1",
    )
    repository.get_automatic = AsyncMock(return_value=None)
    repository.lock_numbering = AsyncMock(return_value=organization)
    repository.advance_numbering = AsyncMock(return_value=7)
    repository.create = AsyncMock(return_value=created_quote)
    repository.add_items = AsyncMock()
    repository.record_automatic_creation = AsyncMock()
    deal_repository.get_sales_customer = AsyncMock(return_value=(company, contact))
    deal_repository.list_deal_products = AsyncMock(return_value=[line])
    monkeypatch.setattr(
        "app.services.quote_service.invoice_repository.get_product_scoped",
        AsyncMock(return_value=product),
    )
    monkeypatch.setattr(
        "app.services.quote_service.NotificationRepository.create_for_scoped_user",
        AsyncMock(),
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_from_won_deal(db, deal=deal, actor_id="user-1")

    assert result.quote_number == "QUO-2026-000007"
    created_data = repository.create.await_args.kwargs["data"]
    assert created_data["organization_id"] == "org-1"
    assert created_data["total_amount"] == 1062
    item = repository.add_items.await_args.args[1][0]
    assert item["product_name"] == "CRM License"
    assert item["total"] == 1062


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
        payload=QuoteBase(deal_id="deal-1", quote_number="Q-2", total_amount=1200, status="Draft"),
    )

    repository.get_scoped.assert_awaited_once_with(db, quote_id="quote-1", organization_id="org-1")
    deal_repository.get_by_id_scoped.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )
    assert result["quote_number"] == "Q-2"
    assert quote.status == "Draft"


@pytest.mark.asyncio
@pytest.mark.parametrize("protected_status", ["Sent", "Accepted", "Rejected"])
async def test_update_quote_cannot_bypass_delivery_or_customer_decision(protected_status):
    quote = make_quote()
    service, _, _ = make_service(quote=quote, deal=make_deal())
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.update_quote(
            db,
            quote_id="quote-1",
            organization_id="org-1",
            payload=QuoteBase(
                deal_id="deal-1",
                quote_number="Q-2",
                total_amount=1200,
                status=protected_status,
            ),
        )

    assert exc_info.value.code == "INVALID_QUOTE_TRANSITION"
    assert quote.status == "Draft"
    db.commit.assert_not_awaited()


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
                status="Draft",
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
async def test_quote_actions_do_not_fabricate_documents(monkeypatch):
    service, _, _ = make_service(quote=make_quote())
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="secure acceptance"):
        await service.accept_quote(db, quote_id="quote-1", organization_id="org-1")
    rejected = await service.reject_quote(
        db,
        quote_id="quote-1",
        reason="Budget constraints",
        organization_id="org-1",
    )
    with pytest.raises(NotFoundError):
        await service.get_quote_pdf(db, quote_id="quote-1", organization_id="org-1")
    monkeypatch.setattr(
        "app.services.quote_service.invoice_repository.get_by_quote", AsyncMock(return_value=None)
    )
    with pytest.raises(APIException):
        await service.convert_quote_to_invoice(db, quote_id="quote-1", organization_id="org-1")
    with pytest.raises(APIException):
        await service.create_quote_revision(db, quote_id="quote-1", organization_id="org-1")
    with pytest.raises(APIException) as revisions_error:
        await service.get_quote_revisions(db, quote_id="quote-1", organization_id="org-1")

    assert rejected["message"].endswith("Budget constraints")
    assert revisions_error.value.status_code == 501


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
