from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.repositories.payment_repository import PaymentRepository
from app.services.invoice_delivery_service import InvoiceDeliveryService


def _invoice(**overrides):
    values = {
        "id": "invoice-1",
        "organization_id": "org-1",
        "invoice_number": "INV-2026-000001",
        "currency": "INR",
        "amount": Decimal("1250.00"),
        "paid_amount": Decimal("0.00"),
        "status": "Pending",
        "recipient_email": "buyer@example.com",
        "stripe_checkout_url": "https://checkout.stripe.com/session",
        "last_reminded_at": None,
        "reminder_count": 0,
        "due_date": datetime.now(UTC) + timedelta(days=7),
        "pdf_s3_key": "org-1/invoices/invoice-1/invoice.pdf",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_pdf_url_uses_tenant_scoped_invoice_lookup(monkeypatch):
    invoice = _invoice()
    db = AsyncMock(spec=AsyncSession)
    get_scoped = AsyncMock(return_value=invoice)
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.invoice_repository.get_scoped", get_scoped
    )

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr("app.services.invoice_delivery_service.asyncio.to_thread", run_inline)
    presign = MagicMock(return_value="https://storage.example/invoice.pdf")
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.s3_service.generate_presigned_url", presign
    )

    result = await InvoiceDeliveryService().pdf_url(
        db, invoice_id="invoice-1", organization_id="org-1"
    )

    assert result == "https://storage.example/invoice.pdf"
    get_scoped.assert_awaited_once_with(db, invoice_id="invoice-1", organization_id="org-1")
    presign.assert_called_once_with(invoice.pdf_s3_key, 3600)


@pytest.mark.asyncio
async def test_payment_reminder_records_only_confirmed_delivery(monkeypatch):
    invoice = _invoice()
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_invoice = AsyncMock(return_value=invoice)
    service = InvoiceDeliveryService()
    service.payment_repository = repository
    db = AsyncMock(spec=AsyncSession)
    record_reminder = AsyncMock()
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.invoice_repository.record_reminder",
        record_reminder,
    )
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.settings.BREVO_API_KEY", "configured"
    )

    async def run_inline(function, *args, **kwargs):
        assert kwargs["idempotency_key"].startswith("invoice-reminder-invoice-1-")
        return "provider-message-1"

    monkeypatch.setattr("app.services.invoice_delivery_service.asyncio.to_thread", run_inline)

    result = await service.send_reminder(db, invoice_id="invoice-1", organization_id="org-1")

    assert result["status"] == "success"
    assert result["provider_message_id"] == "provider-message-1"
    repository.lock_invoice.assert_awaited_once_with(
        db, invoice_id="invoice-1", organization_id="org-1"
    )
    record_reminder.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_reminder_rejects_duplicate_within_24_hours():
    invoice = _invoice(last_reminded_at=datetime.now(UTC))
    repository = MagicMock(spec=PaymentRepository)
    repository.lock_invoice = AsyncMock(return_value=invoice)
    service = InvoiceDeliveryService()
    service.payment_repository = repository
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ConflictError, match="last 24 hours"):
        await service.send_reminder(db, invoice_id="invoice-1", organization_id="org-1")


@pytest.mark.asyncio
async def test_payment_reminder_marks_past_due_invoice_overdue(monkeypatch):
    service = InvoiceDeliveryService()
    invoice = _invoice(due_date=datetime.now(UTC) - timedelta(days=1))
    db = AsyncMock()
    monkeypatch.setattr(service.payment_repository, "lock_invoice", AsyncMock(return_value=invoice))
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.invoice_repository.record_reminder", AsyncMock()
    )
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.settings.BREVO_API_KEY", "configured"
    )

    async def run_inline(function, *args, **kwargs):
        return "message-1"

    monkeypatch.setattr("app.services.invoice_delivery_service.asyncio.to_thread", run_inline)

    await service.send_reminder(db, invoice_id="invoice-1", organization_id="org-1")

    assert invoice.status == "Overdue"


@pytest.mark.asyncio
async def test_payment_reminder_stops_after_three_confirmed_deliveries(monkeypatch):
    service = InvoiceDeliveryService()
    invoice = _invoice(reminder_count=3)
    monkeypatch.setattr(service.payment_repository, "lock_invoice", AsyncMock(return_value=invoice))
    db = AsyncMock()

    with pytest.raises(ConflictError):
        await service.send_reminder(db, invoice_id="invoice-1", organization_id="org-1")

    db.commit.assert_not_awaited()
