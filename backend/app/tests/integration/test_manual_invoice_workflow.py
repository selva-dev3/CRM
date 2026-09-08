"""Real PostgreSQL lifecycle and payment tests; external delivery is stubbed."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.core.errors import APIException, ConflictError, NotFoundError, register_exception_handlers
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models import AuditLog, Invoice, Organization, Payment
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.crm_schemas import ManualPaymentCreate
from app.services.invoice_delivery_service import InvoiceDeliveryService
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.services.public_invoice_service import PublicInvoiceService
from app.services.public_invoice_token import acceptance_token
from app.services.quote_service import QuoteService
from app.tests.integration.test_sales_quote_workflow import (
    prepare_customer_acceptance,
)
from app.tests.integration.test_sales_quote_workflow import (
    sales_database as sales_database,
)


@pytest.mark.asyncio
async def test_real_application_startup_and_database_health_without_stripe(sales_database):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.tests.run_isolated_workflow",
        "--startup",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    assert process.returncode == 0, stderr.decode()
    assert b'"startup": "ok"' in stdout
    assert b'"database": "ok"' in stdout
    assert b'"stripe_imports": "blocked"' in stdout


async def draft_invoice(sales_database, *, unit_price=100):
    token, _ = await prepare_customer_acceptance(sales_database, unit_price=unit_price)
    sessions, *_ = sales_database
    async with sessions() as db:
        result = await QuoteService().accept_public_quote(db, token=token)
    return result["invoice_id"]


async def sent_invoice(sales_database, monkeypatch, *, unit_price=100):
    invoice_id = await draft_invoice(sales_database, unit_price=unit_price)
    sessions, org, user, _, contact, *_ = sales_database
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.s3_service.upload_file",
        Mock(return_value="test-invoice.pdf"),
    )
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.s3_service.generate_presigned_url",
        Mock(return_value="https://storage.example.test/invoice.pdf"),
    )
    monkeypatch.setattr(
        "app.services.invoice_delivery_service.send_tracked_email",
        Mock(return_value="invoice-provider-receipt"),
    )
    async with sessions() as db:
        await InvoiceService().submit_for_review(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        await InvoiceService().finalize_invoice(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        await InvoiceService().mark_sent(
            db, invoice_id=invoice_id, organization_id=org.id, recipient_email=contact.email
        )
    await InvoiceDeliveryService().deliver_one(sessions)
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.delivery_status == "Sent"
        assert invoice.sent_at is not None
        return invoice_id, acceptance_token(invoice.id, invoice.delivery_id)


async def accepted_invoice(sales_database, monkeypatch, *, unit_price=100):
    invoice_id, token = await sent_invoice(sales_database, monkeypatch, unit_price=unit_price)
    sessions, *_ = sales_database
    async with sessions() as db:
        await PublicInvoiceService().accept(db, token=token)
    return invoice_id


async def pay(sales_database, invoice_id, amount, key=None, organization_id=None):
    sessions, org, user, *_ = sales_database
    async with sessions() as db:
        return await PaymentService().record_payment(
            db,
            invoice_id=invoice_id,
            organization_id=organization_id or org.id,
            user_id=user.id,
            payload=ManualPaymentCreate(
                amount=amount,
                payment_type="Bank Transfer",
                payment_date=datetime.now(UTC).date(),
                notes="Customer bank transfer",
            ),
            idempotency_key=key or str(uuid4()),
        )


@pytest.mark.asyncio
async def test_draft_requires_finalize_and_acceptance_before_payment(sales_database):
    invoice_id = await draft_invoice(sales_database)
    sessions, org, user, _, contact, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.status == "Draft"
        assert invoice.payment_status == "Pending"
        assert invoice.delivery_status is None
        assert invoice.finalized_at is None
    async with sessions() as db:
        with pytest.raises(ConflictError):
            await InvoiceService().mark_sent(
                db, invoice_id=invoice_id, organization_id=org.id, recipient_email=contact.email
            )
    with pytest.raises(ConflictError):
        await pay(sales_database, invoice_id, "10")
    async with sessions() as db:
        with pytest.raises(ConflictError):
            await InvoiceService().finalize_invoice(
                db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
            )
        submitted = await InvoiceService().submit_for_review(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        assert submitted["status"] == "In Review"
        finalized = await InvoiceService().finalize_invoice(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        assert finalized["status"] == "Finalized"
        assert finalized["finalized_by"] == user.id
        assert finalized["delivery_status"] is None
    with pytest.raises(ConflictError):
        await pay(sales_database, invoice_id, "10")
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
            )
            == 0
        )
        with pytest.raises(ConflictError):
            await InvoiceService().finalize_invoice(
                db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
            )


@pytest.mark.asyncio
async def test_public_http_view_accept_and_replay_are_safe(sales_database, monkeypatch):
    from app.api.v1.routers.public_invoices import router

    invoice_id, token = await sent_invoice(sales_database, monkeypatch)
    sessions, org, *_ = sales_database
    app = FastAPI()
    app.state.limiter = limiter
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/public/invoices")

    async def database_override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post("/api/v1/public/invoices/view", json={"token": "short"})
        ).status_code == 422
        assert (
            await client.post("/api/v1/public/invoices/view", json={"token": "0" * 64})
        ).status_code == 404
        view = await client.post("/api/v1/public/invoices/view", json={"token": token})
        assert view.status_code == 200
        assert view.json()["status"] == "Finalized"
        assert view.json()["items"][0]["unit_price"] == "100.00"
        assert (
            not {"id", "organization_id", "public_token_hash", "delivery_id", "finalized_by"}
            & view.json().keys()
        )
        accepted = await client.post("/api/v1/public/invoices/accept", json={"token": token})
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "Accepted"
        assert accepted.json()["payment_status"] == "Pending"
        async with sessions() as db:
            summaries = await PaymentService().list_invoice_summaries(
                db, organization_id=org.id, page=1, limit=20
            )
            assert len(summaries) == 1
            assert summaries[0]["invoice_id"] == invoice_id
            assert summaries[0]["payment_status"] == "Pending"
            assert summaries[0]["paid_amount"] == Decimal("0.00")
            assert summaries[0]["outstanding_amount"] == Decimal("200.00")
            assert summaries[0]["latest_payment_id"] is None
            assert summaries[0]["payment_date"] is None
        again = await client.post("/api/v1/public/invoices/accept", json={"token": token})
        assert again.json() == accepted.json()
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.organization_id == org.id, AuditLog.action == "invoice.accepted")
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("already_accepted", [False, True])
async def test_expired_invoice_token_rejected_even_after_acceptance(
    sales_database, monkeypatch, already_accepted
):
    invoice_id, token = await sent_invoice(sales_database, monkeypatch)
    sessions, *_ = sales_database
    async with sessions() as db:
        if already_accepted:
            await PublicInvoiceService().accept(db, token=token)
        invoice = await db.get(Invoice, invoice_id)
        accepted_at = invoice.accepted_at
        invoice.public_token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    for method in ("view", "accept"):
        async with sessions() as db:
            with pytest.raises(APIException) as exc:
                await getattr(PublicInvoiceService(), method)(db, token=token)
            assert exc.value.status_code == 410
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.accepted_at == accepted_at
        assert invoice.status == ("Accepted" if already_accepted else "Finalized")


@pytest.mark.asyncio
@pytest.mark.parametrize("amounts", [["200.00"], ["40.10", "59.90", "100.00"]])
async def test_full_and_multiple_partial_payments_persist_exact_balances(
    sales_database, monkeypatch, amounts
):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    sessions, org, user, *_ = sales_database
    total = Decimal(0)
    numbers = set()
    for amount in amounts:
        result = await pay(sales_database, invoice_id, amount)
        total += Decimal(amount)
        assert result["status"] == "Succeeded"
        assert result["payment_type"] == "Bank Transfer"
        numbers.add(result["payment_number"])
        async with sessions() as db:
            invoice = await db.get(Invoice, invoice_id)
            assert invoice.paid_amount == total
            assert invoice.status == "Accepted"
            assert invoice.payment_status == ("Paid" if total == 200 else "Partially Paid")
            summaries = await PaymentService().list_invoice_summaries(
                db, organization_id=org.id, page=1, limit=20
            )
            summary = next(item for item in summaries if item["invoice_id"] == invoice_id)
            assert summary["paid_amount"] == total
            assert summary["outstanding_amount"] == Decimal("200.00") - total
            assert summary["payment_status"] == (
                "Paid" if total == Decimal("200.00") else "Partially Paid"
            )
            assert summary["latest_payment_id"] == result["id"]
            payment = await db.get(Payment, result["id"])
            assert payment.recorded_by == user.id
            assert payment.receipt_delivery_status == "Pending"
    assert len(numbers) == len(amounts)
    with pytest.raises(ConflictError):
        await pay(sales_database, invoice_id, "0.01")
    async with sessions() as db:
        assert await db.scalar(
            select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice_id)
        ) == Decimal("200.00")
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.organization_id == org.id, AuditLog.action == "invoice.paid")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_concurrent_identical_payment_requests_create_one_payment(
    sales_database, monkeypatch
):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    results = await asyncio.gather(
        *(pay(sales_database, invoice_id, "200.00", "same-key") for _ in range(3))
    )
    assert results[0] == results[1] == results[2]
    with pytest.raises(ConflictError, match="different payment"):
        await pay(sales_database, invoice_id, "100.00", "same-key")
    sessions, *_ = sales_database
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
            )
            == 1
        )
        assert (await db.get(Invoice, invoice_id)).paid_amount == Decimal("200.00")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "amount,successes,total", [("100.00", 2, "200.00"), ("150.00", 1, "150.00")]
)
async def test_concurrent_distinct_payments_serialize_outstanding_balance(
    sales_database, monkeypatch, amount, successes, total
):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    results = await asyncio.gather(
        pay(sales_database, invoice_id, amount),
        pay(sales_database, invoice_id, amount),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == successes
    assert all(isinstance(result, (dict, ConflictError)) for result in results)
    sessions, *_ = sales_database
    async with sessions() as db:
        assert await db.scalar(
            select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice_id)
        ) == Decimal(total)
        assert (await db.get(Invoice, invoice_id)).paid_amount == Decimal(total)


@pytest.mark.asyncio
async def test_foreign_org_cannot_record_or_read_payment(sales_database, monkeypatch):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    foreign_org = str(uuid4())
    with pytest.raises(NotFoundError):
        await pay(sales_database, invoice_id, "10.00", organization_id=foreign_org)
    payment = await pay(sales_database, invoice_id, "10.00")
    sessions, *_ = sales_database
    async with sessions() as db:
        assert (
            await PaymentService().get_payment(
                db, payment_id=payment["id"], organization_id=foreign_org
            )
            is None
        )
        assert (
            await PaymentService().list_payments(
                db, organization_id=foreign_org, page=1, limit=20, invoice_id=invoice_id
            )
            == []
        )
        assert (
            await PaymentService().list_invoice_summaries(
                db, organization_id=foreign_org, page=1, limit=20
            )
            == []
        )


@pytest.mark.asyncio
async def test_payment_transaction_failure_leaves_no_partial_payment(sales_database, monkeypatch):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    monkeypatch.setattr(
        "app.repositories.payment_repository.PaymentRepository.record_manual_audit",
        AsyncMock(side_effect=RuntimeError("audit unavailable")),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await pay(sales_database, invoice_id, "10.00")
    sessions, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.paid_amount == 0
        assert invoice.payment_status == "Pending"
        assert (
            await db.scalar(
                select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_financial_report_uses_real_partial_payments_and_overdue_balance(
    sales_database, monkeypatch
):
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    sessions, org, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        invoice.due_date = datetime.now(UTC) - timedelta(days=1)
        await db.commit()
    await pay(sales_database, invoice_id, "40.10")
    await pay(sales_database, invoice_id, "59.90")
    async with sessions() as db:
        report = await ReportRepository().financial_overview(db, org.id)
        assert report["collected_revenue"] == 100
        assert report["invoice_paid_value"] == 100
        assert report["outstanding_amount"] == 100
        assert report["overdue_amount"] == 100
        assert report["payment_count"] == 2
        foreign = await ReportRepository().financial_overview(db, str(uuid4()))
        assert foreign["collected_revenue"] == foreign["outstanding_amount"] == 0
    await pay(sales_database, invoice_id, "100.00")
    async with sessions() as db:
        report = await ReportRepository().financial_overview(db, org.id)
        assert report["collected_revenue"] == 200
        assert report["outstanding_amount"] == report["overdue_amount"] == 0
        assert (await db.get(Invoice, invoice_id)).status == "Accepted"


@pytest.mark.asyncio
async def test_http_manual_payment_validation_permission_and_tenant_scope(
    sales_database, monkeypatch
):
    from app.api.v1.deps import get_current_user
    from app.api.v1.routers.invoices import router
    from app.api.v1.routers.payments import router as payments_router
    from app.services.auth_service import auth_service

    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    sessions, _, user, *_ = sales_database
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/invoices")
    app.include_router(payments_router, prefix="/api/v1/payments")

    async def database_override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    permission = AsyncMock(return_value=[])
    monkeypatch.setattr(auth_service, "get_user_permissions", permission)
    payload = {
        "amount": "40.10",
        "payment_type": "Cash",
        "payment_date": datetime.now(UTC).date().isoformat(),
    }
    headers = {"Idempotency-Key": "http-payment"}
    endpoint = f"/api/v1/invoices/{invoice_id}/payments"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post(endpoint, json=payload, headers=headers)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert (await client.post(endpoint, json=payload, headers=headers)).status_code == 403
        permission.return_value = ["invoices:payment", "invoices:read"]
        pending = await client.get("/api/v1/payments/invoice-summaries")
        assert pending.status_code == 200
        assert pending.headers["X-Total-Count"] == "1"
        assert pending.json()[0]["payment_status"] == "Pending"
        assert pending.json()[0]["paid_amount"] == 0
        assert pending.json()[0]["outstanding_amount"] == 200
        assert pending.json()[0]["payment_number"] is None
        assert (await client.post(endpoint, json=payload)).status_code == 422
        assert (
            await client.post(endpoint, json=payload | {"amount": "-1"}, headers=headers)
        ).status_code == 422
        assert (
            await client.post(
                endpoint, json=payload | {"organization_id": "foreign"}, headers=headers
            )
        ).status_code == 422
        assert (
            await client.post(f"/api/v1/invoices/{uuid4()}/payments", json=payload, headers=headers)
        ).status_code == 404
        response = await client.post(endpoint, json=payload, headers=headers)
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["status"] == "Succeeded"
        assert result["amount"] == 40.1
        replay = await client.post(endpoint, json=payload, headers=headers)
        assert replay.json() == result
        assert (
            await client.post(endpoint, json=payload | {"amount": "50"}, headers=headers)
        ).status_code == 409
        listed = await client.get(f"/api/v1/payments?invoice_id={invoice_id}")
        assert listed.status_code == 200
        assert [payment["id"] for payment in listed.json()] == [result["id"]]
        summary = await client.get("/api/v1/payments/invoice-summaries")
        assert summary.json()[0]["payment_status"] == "Partially Paid"
        assert summary.json()[0]["paid_amount"] == 40.1
        assert summary.json()[0]["outstanding_amount"] == 159.9
        assert summary.json()[0]["latest_payment_id"] == result["id"]
        async with sessions() as db:
            other_org = Organization(
                id=str(uuid4()), name=f"Other invoice test tenant {uuid4()}", currency="INR"
            )
            db.add(other_org)
            await db.commit()
        original_org = user.organization_id
        user.organization_id = other_org.id
        try:
            assert (await client.post(endpoint, json=payload, headers=headers)).status_code == 404
            assert (await client.get(f"/api/v1/payments/{result['id']}")).status_code == 404
            assert (await client.get(f"/api/v1/payments?invoice_id={invoice_id}")).json() == []
            assert (await client.get("/api/v1/payments/invoice-summaries")).json() == []
        finally:
            user.organization_id = original_org
            async with sessions() as db:
                await db.execute(delete(Organization).where(Organization.id == other_org.id))
                await db.commit()


@pytest.mark.asyncio
async def test_concurrent_public_acceptance_records_one_event(sales_database, monkeypatch):
    invoice_id, token = await sent_invoice(sales_database, monkeypatch)
    sessions, org, *_ = sales_database

    async def accept():
        async with sessions() as db:
            return await PublicInvoiceService().accept(db, token=token)

    first, second = await asyncio.gather(accept(), accept())
    assert first == second
    async with sessions() as db:
        assert (await db.get(Invoice, invoice_id)).status == "Accepted"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.organization_id == org.id, AuditLog.action == "invoice.accepted")
            )
            == 1
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_field", ["billing_snapshot", "currency", "amount"])
async def test_finalize_rejects_invalid_snapshot_without_transition(sales_database, invalid_field):
    invoice_id = await draft_invoice(sales_database)
    sessions, org, user, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        await InvoiceService().submit_for_review(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        invoice = await db.get(Invoice, invoice_id)
        setattr(
            invoice,
            invalid_field,
            {"billing_snapshot": {}, "currency": "invalid", "amount": Decimal("199.00")}[
                invalid_field
            ],
        )
        await db.commit()
    async with sessions() as db:
        with pytest.raises(APIException):
            await InvoiceService().finalize_invoice(
                db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
            )
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.status == "In Review"
        assert invoice.finalized_at is None
        assert invoice.delivery_status is None


@pytest.mark.asyncio
async def test_inr_10000_invoice_two_5000_bank_transfers(sales_database, monkeypatch):
    invoice_id = await accepted_invoice(sales_database, monkeypatch, unit_price=5000)
    sessions, org, *_ = sales_database
    for expected_paid, expected_balance, expected_status in [
        (Decimal("5000.00"), Decimal("5000.00"), "Partially Paid"),
        (Decimal("10000.00"), Decimal("0.00"), "Paid"),
    ]:
        result = await pay(sales_database, invoice_id, "5000.00")
        assert result["payment_type"] == "Bank Transfer"
        assert result["status"] == "Succeeded"
        async with sessions() as db:
            invoice = await db.get(Invoice, invoice_id)
            assert invoice.currency == "INR"
            assert invoice.amount == Decimal("10000.00")
            assert invoice.paid_amount == expected_paid
            assert invoice.amount - invoice.paid_amount == expected_balance
            assert invoice.payment_status == expected_status
            assert invoice.status == "Accepted"
            payments = list(
                (await db.scalars(select(Payment).where(Payment.invoice_id == invoice_id))).all()
            )
            assert sum(payment.amount for payment in payments) == expected_paid
            report = await ReportRepository().financial_overview(db, org.id)
            assert Decimal(str(report["collected_revenue"])) == expected_paid
            assert Decimal(str(report["outstanding_amount"])) == expected_balance


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["city", "state", "postal_code"])
async def test_finalize_rejects_nontext_optional_address(sales_database, field):
    invoice_id = await draft_invoice(sales_database)
    sessions, org, user, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        await InvoiceService().submit_for_review(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        invoice = await db.get(Invoice, invoice_id)
        invoice.billing_snapshot = invoice.billing_snapshot | {field: {"unexpected": "object"}}
        await db.commit()
    async with sessions() as db:
        with pytest.raises(APIException, match="must be text"):
            await InvoiceService().finalize_invoice(
                db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
            )
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.status == "In Review"
        assert invoice.finalized_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "Customer address"])
async def test_finalize_allows_text_or_null_optional_address(sales_database, value):
    invoice_id = await draft_invoice(sales_database)
    sessions, org, user, *_ = sales_database
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        invoice.billing_snapshot = invoice.billing_snapshot | dict.fromkeys(
            ("city", "state", "postal_code"), value
        )
        await db.commit()
        await InvoiceService().submit_for_review(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        result = await InvoiceService().finalize_invoice(
            db, invoice_id=invoice_id, organization_id=org.id, user_id=user.id
        )
        assert result["status"] == "Finalized"


@pytest.mark.asyncio
async def test_reminder_candidates_require_finalization_and_unexpired_link(sales_database):
    sessions, org, *_ = sales_database
    now = datetime.now(UTC)
    ids = {}
    async with sessions() as db:
        for case, finalized_at, expiry in [
            ("eligible", now, now + timedelta(days=1)),
            ("expired", now, now - timedelta(seconds=1)),
            ("exact_expiry", now, now),
            ("no_expiry", now, None),
            ("unfinalized", None, now + timedelta(days=1)),
        ]:
            ids[case] = str(uuid4())
            db.add(
                Invoice(
                    id=ids[case],
                    organization_id=org.id,
                    invoice_number=f"REM-{case}",
                    amount=Decimal("100"),
                    paid_amount=Decimal("50"),
                    currency="INR",
                    status="Accepted",
                    finalized_at=finalized_at,
                    public_token_expires_at=expiry,
                    due_date=now,
                    delivery_status="Sent",
                    sent_at=now,
                )
            )
        await db.commit()
        candidates = await InvoiceRepository().list_due_reminder_candidates(
            db, now=now, limit=10000
        )
        own_ids = {
            invoice_id for invoice_id, organization_id in candidates if organization_id == org.id
        }
        assert own_ids == {ids["eligible"]}
