from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.repositories.payment_repository import PaymentRepository
from app.schemas.crm_schemas import ManualPaymentCreate
from app.services.payment_service import PaymentService


def payment_payload(amount="40.00", **kwargs):
    return ManualPaymentCreate(
        amount=amount,
        payment_type="Cash",
        payment_date=kwargs.get("payment_date", datetime.now(UTC).date()),
    )


@pytest.fixture
def payment_context(monkeypatch):
    invoice = SimpleNamespace(
        id="invoice",
        organization_id="org",
        amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        currency="INR",
        status="Accepted",
        payment_status="Pending",
        finalized_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
    )
    repo = MagicMock(spec=PaymentRepository)
    repo.lock_invoice = AsyncMock(return_value=invoice)
    repo.get_by_idempotency = AsyncMock(return_value=None)
    repo.sum_succeeded = AsyncMock(side_effect=lambda *args, **kwargs: invoice.paid_amount)
    repo.advance_numbering = AsyncMock(return_value=("PAY", 1))
    repo.create_manual = AsyncMock(return_value=SimpleNamespace(id="payment"))
    repo.record_manual_audit = AsyncMock()
    service = PaymentService(repo)
    monkeypatch.setattr(
        service, "get_payment", AsyncMock(return_value={"id": "payment", "status": "Succeeded"})
    )
    return service, repo, invoice, AsyncMock(spec=AsyncSession)


async def record(context, payload=None, key="request-1"):
    service, _, _, db = context
    return await service.record_payment(
        db,
        invoice_id="invoice",
        organization_id="org",
        user_id="user",
        payload=payload or payment_payload(),
        idempotency_key=key,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "amount,prior,expected",
    [
        ("40.00", "0.00", "Partially Paid"),
        ("100.00", "0.00", "Paid"),
        ("60.00", "40.00", "Paid"),
    ],
)
async def test_manual_payment_updates_balance_without_changing_lifecycle(
    payment_context, amount, prior, expected
):
    _, repo, invoice, db = payment_context
    invoice.paid_amount = Decimal(prior)
    result = await record(payment_context, payment_payload(amount))
    assert result["status"] == "Succeeded"
    assert invoice.paid_amount == Decimal(prior) + Decimal(amount)
    assert invoice.payment_status == expected
    assert invoice.status == "Accepted"
    data = repo.create_manual.await_args.kwargs["data"]
    assert data["amount"] == Decimal(amount)
    assert data["recorded_by"] == "user"
    assert data["payment_type"] == "Cash"
    assert data["receipt_delivery_status"] == "Pending"
    assert data["payment_number"].endswith("-000001")
    repo.record_manual_audit.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["Draft", "Finalized", "Cancelled"])
async def test_payment_requires_customer_acceptance(payment_context, status):
    _, repo, invoice, db = payment_context
    invoice.status = status
    with pytest.raises(ConflictError) as exc:
        await record(payment_context)
    assert exc.value.code == "INVOICE_ACCEPTANCE_REQUIRED"
    repo.create_manual.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["finalized_at", "accepted_at"])
async def test_payment_requires_lifecycle_evidence(payment_context, missing):
    _, repo, invoice, _ = payment_context
    setattr(invoice, missing, None)
    with pytest.raises(ConflictError):
        await record(payment_context)
    repo.create_manual.assert_not_awaited()


@pytest.mark.asyncio
async def test_payment_rejects_overpayment_without_writes(payment_context):
    _, repo, invoice, db = payment_context
    invoice.paid_amount = Decimal("80.00")
    with pytest.raises(ConflictError, match="outstanding") as exc:
        await record(payment_context)
    assert exc.value.code == "PAYMENT_EXCEEDS_BALANCE"
    assert invoice.paid_amount == Decimal("80.00")
    repo.advance_numbering.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_rejects_foreign_invoice(payment_context):
    _, repo, _, db = payment_context
    repo.lock_invoice.return_value = None
    with pytest.raises(NotFoundError):
        await record(payment_context)
    repo.lock_invoice.assert_awaited_once_with(db, invoice_id="invoice", organization_id="org")
    repo.create_manual.assert_not_awaited()


@pytest.mark.asyncio
async def test_payment_rejects_future_date(payment_context):
    with pytest.raises(APIException, match="future"):
        await record(
            payment_context,
            payment_payload(payment_date=datetime.now(UTC).date() + timedelta(days=1)),
        )
    payment_context[1].create_manual.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "  ", "x" * 129])
async def test_payment_requires_bounded_idempotency_key(payment_context, key):
    with pytest.raises(APIException):
        await record(payment_context, key=key)
    payment_context[1].lock_invoice.assert_not_awaited()


@pytest.mark.asyncio
async def test_payment_replay_after_full_payment_does_not_duplicate(payment_context):
    _, repo, invoice, _ = payment_context
    first = await record(payment_context, payment_payload("100.00"))
    digest = repo.create_manual.await_args.kwargs["data"]["request_hash"]
    repo.get_by_idempotency.return_value = SimpleNamespace(id="payment", request_hash=digest)
    second = await record(payment_context, payment_payload("100"))
    assert second == first
    assert invoice.paid_amount == Decimal("100.00")
    repo.create_manual.assert_awaited_once()
    repo.record_manual_audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_rejects_reused_key_with_changed_payload(payment_context):
    _, repo, _, db = payment_context
    repo.get_by_idempotency.return_value = SimpleNamespace(id="payment", request_hash="different")
    with pytest.raises(ConflictError, match="different payment") as exc:
        await record(payment_context)
    assert exc.value.code == "PAYMENT_IDEMPOTENCY_CONFLICT"
    repo.create_manual.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_failure_rolls_back_transaction(payment_context):
    _, repo, _, db = payment_context
    repo.record_manual_audit.side_effect = RuntimeError("audit unavailable")
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await record(payment_context)
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
