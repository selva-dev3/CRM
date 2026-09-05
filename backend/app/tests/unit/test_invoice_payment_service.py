from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.repositories.payment_repository import PaymentRepository
from app.services.invoice_payment_service import InvoicePaymentService, stripe_minor_units


@pytest.mark.parametrize(
    "amount,currency,expected", [("100.10", "INR", 10010), ("0.50", "USD", 50)]
)
def test_minor_units_are_exact(amount, currency, expected):
    assert stripe_minor_units(amount, currency) == expected


@pytest.mark.parametrize("amount,currency", [("1.234", "USD"), ("0", "INR"), ("1", "JPY")])
def test_unsupported_or_unpayable_amount_is_rejected(amount, currency):
    with pytest.raises(APIException):
        stripe_minor_units(amount, currency)


@pytest.mark.asyncio
async def test_checkout_uses_persisted_invoice_amount_and_provider_url(monkeypatch):
    invoice = Invoice(
        id="invoice",
        organization_id="org",
        invoice_number="INV-1",
        amount=120,
        paid_amount=0,
        status="Pending",
        currency="INR",
        stripe_checkout_generation=0,
    )
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_invoice = AsyncMock(return_value=invoice)
    repository.save_checkout = AsyncMock()
    service = InvoicePaymentService(repository)
    create = MagicMock(
        return_value=SimpleNamespace(
            id="session", url="https://checkout.stripe.com/test-provider-response"
        )
    )
    client = SimpleNamespace(
        v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=create)))
    )
    monkeypatch.setattr(service, "_client", lambda: client)

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr("app.services.invoice_payment_service.asyncio.to_thread", run_inline)
    db = MagicMock(spec=AsyncSession)
    response = await service.checkout(db, invoice_id="invoice", organization_id="org")
    assert response["checkout_url"] == create.return_value.url
    params, options = create.call_args.args
    assert params["line_items"][0]["price_data"]["unit_amount"] == 12000
    assert params["metadata"] == {"invoice_id": "invoice", "organization_id": "org"}
    assert options["idempotency_key"] == "crm-invoice-invoice-0"
    db.commit.assert_awaited_once()


def _paid_event(*, amount=12000, organization_id="org", event_id="evt-1"):
    session = {
        "id": "session",
        "mode": "payment",
        "payment_status": "paid",
        "payment_intent": "pi-1",
        "payment_method_types": ["card"],
        "currency": "inr",
        "amount_total": amount,
        "metadata": {"invoice_id": "invoice", "organization_id": organization_id},
    }
    return SimpleNamespace(
        id=event_id,
        type="checkout.session.completed",
        data=SimpleNamespace(object=SimpleNamespace(to_dict=lambda: session)),
    )


@pytest.mark.asyncio
async def test_verified_webhook_records_payment_and_marks_invoice_paid(monkeypatch):
    invoice = Invoice(
        id="invoice",
        organization_id="org",
        invoice_number="INV-1",
        amount=120,
        paid_amount=0,
        status="Pending",
        currency="INR",
    )
    payment = Payment(id="payment-1", invoice_id="invoice", organization_id="org")
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_checkout = AsyncMock(return_value=invoice)
    repository.get_payment = AsyncMock(return_value=None)

    async def record_payment(*args, **kwargs):
        invoice.status = "Paid"
        invoice.paid_amount = invoice.amount
        return payment

    repository.record_payment = AsyncMock(side_effect=record_payment)
    service = InvoicePaymentService(repository)
    monkeypatch.setattr(
        "app.services.invoice_payment_service.settings.STRIPE_WEBHOOK_SECRET",
        "webhook-secret",
    )
    monkeypatch.setattr(
        "app.services.invoice_payment_service.stripe.Webhook.construct_event",
        MagicMock(return_value=_paid_event()),
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.webhook(db, payload=b"signed", signature="signature")

    assert result == {
        "received": True,
        "invoice_id": "invoice",
        "payment_id": "payment-1",
        "invoice_status": "Paid",
    }
    repository.record_payment.assert_awaited_once()
    assert repository.record_payment.await_args.kwargs["event_id"] == "evt-1"
    assert repository.record_payment.await_args.kwargs["payment_method"] == "card"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_rejects_cross_tenant_metadata(monkeypatch):
    invoice = Invoice(
        id="invoice",
        organization_id="org",
        invoice_number="INV-1",
        amount=120,
        paid_amount=0,
        status="Pending",
        currency="INR",
    )
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_checkout = AsyncMock(return_value=invoice)
    repository.record_payment = AsyncMock()
    service = InvoicePaymentService(repository)
    monkeypatch.setattr(
        "app.services.invoice_payment_service.settings.STRIPE_WEBHOOK_SECRET",
        "webhook-secret",
    )
    monkeypatch.setattr(
        "app.services.invoice_payment_service.stripe.Webhook.construct_event",
        MagicMock(return_value=_paid_event(organization_id="foreign-org")),
    )
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.webhook(db, payload=b"signed", signature="signature")

    assert exc_info.value.code == "PAYMENT_MISMATCH"
    repository.record_payment.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_webhook_returns_existing_payment(monkeypatch):
    invoice = Invoice(
        id="invoice",
        organization_id="org",
        invoice_number="INV-1",
        amount=120,
        paid_amount=120,
        status="Paid",
        currency="INR",
    )
    existing = Payment(
        id="payment-1",
        invoice_id="invoice",
        organization_id="org",
        provider_payment_id="pi-1",
    )
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_checkout = AsyncMock(return_value=invoice)
    repository.get_payment = AsyncMock(return_value=existing)
    repository.record_payment = AsyncMock()
    service = InvoicePaymentService(repository)
    monkeypatch.setattr(
        "app.services.invoice_payment_service.settings.STRIPE_WEBHOOK_SECRET",
        "webhook-secret",
    )
    monkeypatch.setattr(
        "app.services.invoice_payment_service.stripe.Webhook.construct_event",
        MagicMock(return_value=_paid_event()),
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.webhook(db, payload=b"signed", signature="signature")

    assert result["payment_id"] == "payment-1"
    assert result["invoice_status"] == "Paid"
    repository.record_payment.assert_not_awaited()
