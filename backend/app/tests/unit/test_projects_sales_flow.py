from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, NotFoundError
from app.models import SalesOrder
from app.repositories.order_repository import OrderRepository
from app.repositories.price_book_repository import PriceBookRepository
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate
from app.schemas.price_book import PriceBookUpdate
from app.services.order_service import OrderService
from app.services.price_book_service import PriceBookService


def accepted_quote(**overrides):
    values = {
        "id": "quote-1",
        "organization_id": "org-1",
        "deal_id": "deal-1",
        "company_id": "company-1",
        "contact_id": "contact-1",
        "currency": "USD",
        "status": "Accepted",
        "approved_at": datetime.now(UTC),
        "accepted_at": datetime.now(UTC),
        "total_amount": Decimal("107.00"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def quote_line(**overrides):
    values = {
        "product_id": "product-1",
        "product_name": "Implementation",
        "quantity": 1,
        "unit_price": Decimal("100.00"),
        "discount_percent": Decimal("0"),
        "tax_percent": Decimal("7"),
        "subtotal": Decimal("100.00"),
        "discount_total": Decimal("0"),
        "tax_total": Decimal("7.00"),
        "total": Decimal("107.00"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_order_creation_snapshots_an_accepted_quote_once():
    repository = MagicMock(spec=OrderRepository)
    repository.get_by_quote = AsyncMock(return_value=None)
    repository.lock_numbering = AsyncMock(
        return_value=SimpleNamespace(order_prefix="ORD", order_sequence=9)
    )
    quote_repository = MagicMock()
    quote_repository.list_items = AsyncMock(return_value=[quote_line()])
    service = OrderService(repository=repository, quote_repository=quote_repository)
    db = MagicMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()

    order = await service.ensure_from_accepted_quote(db, accepted_quote())

    assert isinstance(order, SalesOrder)
    assert order.organization_id == "org-1"
    assert order.order_number.endswith("000010")
    assert order.total == Decimal("107.00")
    assert repository.lock_numbering.await_count == 1
    assert db.add_all.call_args.args[0][0].product_name == "Implementation"


@pytest.mark.asyncio
async def test_order_creation_is_idempotent_for_the_same_quote():
    existing = SalesOrder(id="order-1", quote_id="quote-1")
    repository = MagicMock(spec=OrderRepository)
    repository.get_by_quote = AsyncMock(return_value=existing)
    service = OrderService(repository=repository, quote_repository=MagicMock())

    assert await service.ensure_from_accepted_quote(MagicMock(), accepted_quote()) is existing
    repository.lock_numbering.assert_not_called()


@pytest.mark.asyncio
async def test_order_rejects_a_quote_with_a_mismatched_total():
    repository = MagicMock(spec=OrderRepository)
    repository.get_by_quote = AsyncMock(return_value=None)
    repository.lock_numbering = AsyncMock(
        return_value=SimpleNamespace(order_prefix="ORD", order_sequence=0)
    )
    quote_repository = MagicMock()
    quote_repository.list_items = AsyncMock(return_value=[quote_line(total=Decimal("99.00"))])
    service = OrderService(repository=repository, quote_repository=quote_repository)

    with pytest.raises(ConflictError, match="total is invalid"):
        await service.ensure_from_accepted_quote(MagicMock(), accepted_quote())


@pytest.mark.asyncio
async def test_order_lookup_does_not_leak_another_tenant_record():
    repository = MagicMock(spec=OrderRepository)
    repository.get = AsyncMock(return_value=None)
    service = OrderService(repository=repository)
    user = SimpleNamespace(organization_id="org-1")

    with pytest.raises(NotFoundError, match="Order not found"):
        await service.get(MagicMock(), user, "other-org-order")

    repository.get.assert_awaited_once_with(
        ANY, order_id="other-org-order", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_legacy_invoice_is_linked_when_order_is_created_from_quote():
    quote = accepted_quote()
    order = SalesOrder(
        id="order-1",
        quote_id=quote.id,
        organization_id="org-1",
        order_number="ORD-2026-000001",
        status="Confirmed",
        currency="USD",
        subtotal=Decimal("100"),
        discount_total=Decimal("0"),
        tax_total=Decimal("7"),
        total=Decimal("107"),
        confirmed_at=datetime.now(UTC),
    )
    invoice = SimpleNamespace(order_id=None)
    repository = MagicMock(spec=OrderRepository)
    repository.get_quote = AsyncMock(return_value=quote)
    repository.get_by_quote = AsyncMock(return_value=order)
    repository.get_invoice_for_quote = AsyncMock(return_value=invoice)
    repository.list_items = AsyncMock(return_value=[])
    service = OrderService(repository=repository)
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = SimpleNamespace(organization_id="org-1")

    result = await service.create_from_quote(db, user, quote.id)

    assert invoice.order_id == order.id
    assert result["id"] == order.id
    db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (PriceBookUpdate, {"name": None}),
        (PriceBookUpdate, {"currency": None}),
        (MilestoneUpdate, {"name": None}),
        (MilestoneUpdate, {"status": None}),
        (MilestoneCreate, {"project_id": "project-1", "name": "Release", "due_date": "bad-date"}),
        (MilestoneUpdate, {"due_date": "bad-date"}),
    ],
)
def test_project_sales_schemas_reject_invalid_nonnullable_updates(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.asyncio
async def test_price_book_context_returns_tenant_sales_currency():
    repository = MagicMock(spec=PriceBookRepository)
    repository.get_organization_currency = AsyncMock(return_value="inr")
    service = PriceBookService(repository=repository)
    user = SimpleNamespace(organization_id="org-1")

    result = await service.context(MagicMock(), user)

    assert result == {"currency": "INR"}
    repository.get_organization_currency.assert_awaited_once_with(
        ANY, organization_id="org-1"
    )
