from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models.invoice import Invoice
from app.repositories.payment_repository import PaymentRepository
from app.services.invoice_payment_service import InvoicePaymentService, stripe_minor_units


@pytest.mark.parametrize("amount,currency,expected", [("100.10", "INR", 10010), ("0.50", "USD", 50)])
def test_minor_units_are_exact(amount, currency, expected):
    assert stripe_minor_units(amount, currency) == expected


@pytest.mark.parametrize("amount,currency", [("1.234", "USD"), ("0", "INR"), ("1", "JPY")])
def test_unsupported_or_unpayable_amount_is_rejected(amount, currency):
    with pytest.raises(APIException):
        stripe_minor_units(amount, currency)


@pytest.mark.asyncio
async def test_checkout_uses_persisted_invoice_amount_and_provider_url(monkeypatch):
    invoice = Invoice(id="invoice", organization_id="org", invoice_number="INV-1",
                      amount=120, paid_amount=0, status="Pending", currency="INR",
                      stripe_checkout_generation=0)
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_invoice = AsyncMock(return_value=invoice)
    repository.save_checkout = AsyncMock()
    service = InvoicePaymentService(repository)
    create = MagicMock(return_value=SimpleNamespace(id="session", url="https://checkout.stripe.com/test-provider-response"))
    client = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=create))))
    monkeypatch.setattr(service, "_client", lambda: client)
    db = MagicMock(spec=AsyncSession)
    response = await service.checkout(db, invoice_id="invoice", organization_id="org")
    assert response["checkout_url"] == create.return_value.url
    params, options = create.call_args.args
    assert params["line_items"][0]["price_data"]["unit_amount"] == 12000
    assert params["metadata"] == {"invoice_id": "invoice", "organization_id": "org"}
    assert options["idempotency_key"] == "crm-invoice-invoice-0"
    db.commit.assert_awaited_once()
