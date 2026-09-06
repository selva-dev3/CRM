from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.crm_schemas import InvoiceUpdate, ManualPaymentCreate, PublicInvoiceRequest


@pytest.mark.parametrize("payment_type", ["Cash", "Bank Transfer", "Cheque", "Card", "Other"])
def test_manual_payment_preserves_exact_money(payment_type):
    payment = ManualPaymentCreate(
        amount="100.10", payment_type=payment_type, payment_date="2026-09-06"
    )
    assert payment.amount == Decimal("100.10")
    assert payment.payment_date.isoformat() == "2026-09-06"


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "1.001"},
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"amount": "1000000000000.00"},
        {"payment_type": "Stripe"},
        {"payment_date": "not-a-date"},
        {"notes": "x" * 2001},
        {"organization_id": "foreign-org"},
        {"status": "Succeeded"},
        {"paid_amount": "100"},
    ],
)
def test_manual_payment_rejects_invalid_or_server_owned_fields(changes):
    payload = {"amount": "100.10", "payment_type": "Cash", "payment_date": "2026-09-06"}
    with pytest.raises(ValidationError):
        ManualPaymentCreate(**(payload | changes))


@pytest.mark.parametrize("status", ["Paid", "Pending", "Finalized", "Accepted"])
def test_generic_invoice_update_cannot_bypass_lifecycle(status):
    with pytest.raises(ValidationError):
        InvoiceUpdate(status=status)


@pytest.mark.parametrize("token", ["", "a" * 63, "a" * 65, "g" * 64])
def test_public_invoice_token_requires_exact_digest(token):
    with pytest.raises(ValidationError):
        PublicInvoiceRequest(token=token)
