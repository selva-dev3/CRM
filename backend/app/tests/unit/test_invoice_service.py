from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.models import Product, User
from app.models.deal import Deal, DealProduct
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.services.integration_service import integration_service
from app.services.invoice_service import (
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_PENDING,
    DealNotClosedWonError,
    InvoiceService,
)


def _make_user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="rep@crm.com",
        name="Sales Rep",
        role="Sales Executive",
        is_active=True,
    )


def _make_deal(**overrides) -> Deal:
    defaults = {
        "id": "deal-1",
        "organization_id": "org-1",
        "title": "Acme Corp Deal",
        "amount": 25000.0,
        "stage": "Closed Won",
        "probability": 100.0,
        "assigned_to": "user-1",
        "company_id": "comp-1",
        "contact_id": "cont-1",
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Deal(**defaults)


def _make_deal_product(**overrides) -> DealProduct:
    defaults = {
        "id": "dp-1",
        "deal_id": "deal-1",
        "product_id": "prod-1",
        "quantity": 2,
        "unit_price": 500.0,
    }
    defaults.update(overrides)
    return DealProduct(**defaults)


def _make_product(**overrides) -> Product:
    defaults = {
        "id": "prod-1",
        "organization_id": "org-1",
        "name": "Enterprise License",
        "sku": "SKU-LIC",
        "price": 500.0,
    }
    defaults.update(overrides)
    return Product(**defaults)


def _make_invoice(**overrides) -> Invoice:
    defaults = {
        "id": "inv-1",
        "organization_id": "org-1",
        "deal_id": "deal-1",
        "company_id": "comp-1",
        "contact_id": "cont-1",
        "invoice_number": "INV-1001",
        "amount": 1000.0,
        "subtotal": 1000.0,
        "status": INVOICE_STATUS_DRAFT,
        "due_date": datetime(2026, 9, 30, tzinfo=UTC),
        "created_at": datetime(2026, 8, 25, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Invoice(**defaults)


def _service_with(repo: InvoiceRepository) -> InvoiceService:
    return InvoiceService(repository=repo)


@pytest.fixture
def patched_org(monkeypatch):
    from app.services.invoice_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )


@pytest.fixture(autouse=True)
def patched_notify(monkeypatch):
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())


# ---------------------------------------------------------------------------
# Closed Won enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage",
    [
        "Prospecting",
        "Qualification",
        "Proposal",
        "Negotiation",
        "Closed Lost",
    ],
)
async def test_conversion_rejected_before_closed_won(stage, patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal(stage=stage))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(DealNotClosedWonError):
        await service.create_invoice_from_deal(db, "deal-1", _make_user())


@pytest.mark.asyncio
async def test_cross_tenant_deal_cannot_create_invoice(patched_org):
    repo = InvoiceRepository()
    # Deal exists but belongs to another organization -> scoped lookup misses it.
    repo.get_deal_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.create_invoice_from_deal(db, "deal-other-org", _make_user())


# ---------------------------------------------------------------------------
# Happy path mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conversion_maps_customer_and_line_items(patched_org):
    deal = _make_deal()
    product = _make_product()
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=deal)
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=product)
    created_invoice = _make_invoice()
    repo.create = AsyncMock(return_value=created_invoice)

    def _add_items(_db, *, items):
        return [type("I", (), item)() for item in items]

    repo.add_items = AsyncMock(side_effect=_add_items)
    repo.list_items = AsyncMock(
        return_value=[
            type(
                "Item",
                (),
                {
                    "id": "it-1",
                    "product_id": "prod-1",
                    "description": "Enterprise License",
                    "quantity": 2,
                    "unit_price": 500.0,
                    "discount_percent": 0.0,
                    "tax_percent": 0.0,
                },
            )()
        ]
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert result["company_id"] == "comp-1"
    assert result["contact_id"] == "cont-1"
    assert result["status"] == INVOICE_STATUS_DRAFT
    assert result["paid_amount"] == 0.0
    assert result["amount"] == 1000.0
    assert result["subtotal"] == 1000.0
    assert len(result["items"]) == 1
    assert result["items"][0]["product_id"] == "prod-1"
    assert result["items"][0]["quantity"] == 2
    assert result["items"][0]["unit_price"] == 500.0

    created_kwargs = repo.create.await_args.kwargs["data"]
    assert created_kwargs["organization_id"] == "org-1"
    assert created_kwargs["status"] == INVOICE_STATUS_DRAFT
    assert created_kwargs["deal_id"] == "deal-1"
    assert created_kwargs["currency"] == "USD"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversion_computes_totals_server_side(patched_org):
    """Client-supplied numbers are ignored; totals derive from line items."""
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(
        return_value=[
            _make_deal_product(product_id="p1", quantity=3, unit_price=199.99),
            _make_deal_product(id="dp-2", product_id="p2", quantity=1, unit_price=50.05),
        ]
    )

    async def _get_product(db, *, product_id, organization_id):
        return _make_product(id=product_id)

    repo.get_product_scoped = AsyncMock(side_effect=_get_product)
    repo.create = AsyncMock(return_value=_make_invoice())
    repo.add_items = AsyncMock(return_value=[])
    repo.list_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.create_invoice_from_deal(db, "deal-1", _make_user())

    data = repo.create.await_args.kwargs["data"]
    # subtotal = round(3*199.99 + 1*50.05, 2) = round(650.02, 2)
    assert data["subtotal"] == 650.02
    assert data["tax_total"] == 0.0
    assert data["discount_total"] == 0.0
    assert data["amount"] == 650.02


@pytest.mark.asyncio
async def test_creation_leaves_payment_state_unpaid(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())
    repo.create = AsyncMock(return_value=_make_invoice())
    repo.add_items = AsyncMock(return_value=[])
    repo.list_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert result["status"] != INVOICE_STATUS_PAID
    assert result["paid_amount"] == 0.0


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_customer_rejected(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal(company_id=None, contact_id=None))
    repo.get_by_deal = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.create_invoice_from_deal(db, "deal-1", _make_user())
    assert exc_info.value.code == "DEAL_MISSING_CUSTOMER"


@pytest.mark.asyncio
async def test_no_billable_items_rejected(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.create_invoice_from_deal(db, "deal-1", _make_user())
    assert exc_info.value.code == "DEAL_NO_BILLABLE_ITEMS"


@pytest.mark.asyncio
async def test_invalid_quantity_rejected(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product(quantity=0)])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.create_invoice_from_deal(db, "deal-1", _make_user())
    assert exc_info.value.code == "INVALID_LINE_ITEM_QUANTITY"


@pytest.mark.asyncio
async def test_cross_tenant_product_rejected(patched_org):
    """A product belonging to another organization cannot be invoiced."""
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.create_invoice_from_deal(db, "deal-1", _make_user())
    assert exc_info.value.code == "DEAL_PRODUCT_INVALID"


# ---------------------------------------------------------------------------
# Idempotency / duplicate protection / transaction safety
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_conversion_returns_existing_invoice(patched_org):
    existing = _make_invoice()
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=existing)
    repo.list_items = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert result["id"] == "inv-1"
    repo.create.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_conversion_returns_existing_on_unique_violation(patched_org):
    """Second concurrent request loses the unique-index race and reuses the winner."""
    winner = _make_invoice()
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    # 1st call (pre-check): none exists. 2nd call (post-conflict): the concurrent
    # request's invoice is already committed.
    repo.get_by_deal = AsyncMock(side_effect=[None, winner])
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())
    repo.create = AsyncMock(return_value=_make_invoice(id="inv-race"))
    repo.add_items = AsyncMock(return_value=[])
    repo.list_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock(side_effect=IntegrityError("uq_invoices_one_per_deal", None, Exception()))

    result = await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert result["id"] == "inv-1"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_unique_violation_without_winner_raises_conflict(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())
    repo.create = AsyncMock(return_value=_make_invoice(id="inv-race"))
    repo.add_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock(side_effect=IntegrityError("uq_invoices_one_per_deal", None, Exception()))

    with pytest.raises(ConflictError):
        await service.create_invoice_from_deal(db, "deal-1", _make_user())

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_no_partial_invoice(patched_org):
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())
    repo.create = AsyncMock(return_value=_make_invoice())
    repo.add_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock(side_effect=RuntimeError("connection reset"))

    with pytest.raises(APIException) as exc_info:
        await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert exc_info.value.code == "INVOICE_CREATE_FAILED"
    db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Real-DB defect regression: line items must reference the flushed invoice id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_line_items_use_flushed_invoice_id(patched_org):
    """Regression: Invoice.id is generated at flush time (Python-side default), so
    line items must not capture invoice.id before a flush. Found by live E2E QA:
    invoice_items.invoice_id arrived as NULL on real PostgreSQL."""
    repo = InvoiceRepository()
    repo.get_deal_scoped = AsyncMock(return_value=_make_deal())
    repo.get_by_deal = AsyncMock(return_value=None)
    repo.list_deal_products = AsyncMock(return_value=[_make_deal_product()])
    repo.get_product_scoped = AsyncMock(return_value=_make_product())

    captured: list[dict] = []
    invoice = _make_invoice(id=None)  # pre-flush state, like a real unflushed ORM row

    def _add_items(_db, *, items):
        captured.extend(items)
        return items

    async def _flush():
        invoice.id = invoice.id or "inv-flushed"

    repo.create = AsyncMock(return_value=invoice)
    repo.add_items = AsyncMock(side_effect=_add_items)
    repo.list_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.flush = AsyncMock(side_effect=_flush)

    result = await service.create_invoice_from_deal(db, "deal-1", _make_user())

    assert captured and captured[0]["invoice_id"] == "inv-flushed"
    assert db.flush.await_count >= 1
    assert result["id"] == "inv-flushed"


# ---------------------------------------------------------------------------
# Payment lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_promotes_draft_to_pending(patched_org):
    invoice = _make_invoice(status=INVOICE_STATUS_DRAFT)
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=invoice)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_sent(
        db, invoice_id="inv-1", organization_id="org-1", recipient_email="a@b.com"
    )

    assert invoice.status == INVOICE_STATUS_PENDING
    assert invoice.sent_at is not None


@pytest.mark.asyncio
async def test_send_does_not_touch_overdue_or_paid(patched_org):
    invoice = _make_invoice(status="Overdue")
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=invoice)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_sent(db, invoice_id="inv-1", organization_id="org-1", recipient_email="a@b.com")

    assert invoice.status == "Overdue"
    assert invoice.sent_at is not None


@pytest.mark.asyncio
async def test_mark_paid_sets_paid_amount_and_fires_event(patched_org):
    invoice = _make_invoice(status=INVOICE_STATUS_PENDING)
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=invoice)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_paid(
        db, invoice_id="inv-1", organization_id="org-1", payment_method="Stripe"
    )

    assert invoice.status == INVOICE_STATUS_PAID
    assert invoice.paid_amount == 1000.0
    notify = integration_service.notify_slack_event
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "invoice.paid"


@pytest.mark.asyncio
async def test_double_payment_rejected(patched_org):
    invoice = _make_invoice(status=INVOICE_STATUS_PAID, paid_amount=1000.0)
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=invoice)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ConflictError) as exc_info:
        await service.mark_paid(
            db, invoice_id="inv-1", organization_id="org-1", payment_method="Stripe"
        )
    assert exc_info.value.code == "INVOICE_ALREADY_PAID"


@pytest.mark.asyncio
async def test_get_invoice_scoped_by_organization():
    invoice = _make_invoice()
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=invoice)
    repo.list_items = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = MagicMock()

    result = await service.get_invoice(db=db, invoice_id="inv-1", organization_id="org-1")

    assert result["id"] == "inv-1"
    repo.get_scoped.assert_awaited_once_with(db, invoice_id="inv-1", organization_id="org-1")


@pytest.mark.asyncio
async def test_get_invoice_other_org_returns_not_found():
    repo = InvoiceRepository()
    repo.get_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)

    with pytest.raises(NotFoundError):
        await service.get_invoice(db=MagicMock(), invoice_id="inv-1", organization_id="org-B")
