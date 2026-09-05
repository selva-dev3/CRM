"""Real PostgreSQL tests. Use only an isolated migrated crm_workflow_test database.

CRM_WORKFLOW_TEST_DATABASE_URL=postgresql+asyncpg://.../crm_workflow_test pytest ...
Each test creates a distinct tenant; no production tables or records are deleted.
"""

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.models import (
    Company,
    Contact,
    ContactAddress,
    Deal,
    Invoice,
    InvoiceItem,
    Lead,
    Organization,
    Product,
    Quote,
    QuoteItem,
    User,
)
from app.models.payment import Payment
from app.schemas.crm_schemas import LeadConvertRequest
from app.services.deal_service import DealService
from app.services.email_service import EmailDeliveryUnknownError
from app.services.invoice_payment_service import InvoicePaymentService
from app.services.lead_service import LeadService
from app.services.quote_delivery_service import QuoteDeliveryService, acceptance_token
from app.services.quote_service import QuoteService


@pytest.mark.asyncio
async def test_http_customer_acceptance_contract_and_invalid_token(sales_database):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.routers.public_quotes import router
    from app.core.errors import register_exception_handlers
    from app.core.rate_limiter import limiter
    from app.db.session import get_db

    token, quote_id = await prepare_customer_acceptance(sales_database)
    sessions, *_ = sales_database
    app = FastAPI()
    app.state.limiter = limiter
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/public/quotes")

    async def database_override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/v1/public/quotes/view", json={"token": "short"})).status_code == 422
        assert (await client.post("/api/v1/public/quotes/view", json={"token": secrets.token_urlsafe(32)})).status_code == 404
        view = await client.post("/api/v1/public/quotes/view", json={"token": token})
        assert view.status_code == 200
        assert view.json()["items"][0]["unit_price"] == 100
        assert "public_token_hash" not in view.json()
        accepted = await client.post("/api/v1/public/quotes/accept", json={"token": token})
        assert accepted.status_code == 200
        assert accepted.json()["quote_id"] == quote_id
        assert accepted.json()["invoice_status"] == "Pending"
        again = await client.post("/api/v1/public/quotes/accept", json={"token": token})
        assert again.json() == accepted.json()


@pytest.mark.asyncio
async def test_http_approval_permission_and_tenant_scope(sales_database, monkeypatch):
    from unittest.mock import AsyncMock

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.deps import get_current_user
    from app.api.v1.routers.quotes import router
    from app.core.errors import register_exception_handlers
    from app.db.session import get_db
    from app.services.auth_service import auth_service

    sessions, org, user, _, contact, product, deal = sales_database
    async with sessions() as db:
        await DealService().add_deal_product(db, deal_id=deal.id, product_id=product.id,
            quantity=1, unit_price=100, custom_name=None, organization_id=org.id)
        result = await DealService().mark_deal_won(db, deal.id, None, organization_id=org.id, actor_id=user.id)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/quotes")

    async def database_override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: user
    permission = AsyncMock(return_value=[])
    monkeypatch.setattr(auth_service, "get_user_permissions", permission)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        endpoint = f"/api/v1/quotes/{result['quote_id']}/approve"
        assert (await client.post(endpoint)).status_code == 403
        permission.return_value = ["quotes:approve"]
        user.organization_id = str(uuid4())
        assert (await client.post(endpoint)).status_code == 404
        user.organization_id = org.id
        blocked = await client.post(endpoint)
        assert blocked.status_code == 409
        permission.return_value = ["quotes:send"]
        sent = await client.post(
            f"/api/v1/quotes/{result['quote_id']}/send?recipient_email={contact.email}"
        )
        assert sent.status_code == 202
        assert sent.json()["status"] == "Pending"


@pytest_asyncio.fixture
async def sales_database():
    database_url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(database_url)
    if parsed.host not in {"127.0.0.1", "localhost"} or parsed.database != "crm_workflow_test":
        pytest.fail("Use the dedicated localhost crm_workflow_test database")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with sessions() as db:
        org = Organization(id=str(uuid4()), name="Workflow test tenant", currency="INR")
        user = User(id=str(uuid4()), organization_id=org.id, name="Sales test user",
                    email=f"{uuid4()}@example.test", hashed_password=uuid4().hex, is_active=True)
        company = Company(id=str(uuid4()), organization_id=org.id, name="Test customer")
        contact = Contact(id=str(uuid4()), organization_id=org.id, name="Buyer",
                          email=f"{uuid4()}@example.test", company_id=company.id)
        product = Product(id=str(uuid4()), organization_id=org.id, name="Service",
                          sku=str(uuid4()), price=100, is_active=True)
        db.add(org)
        await db.flush()
        db.add_all([user, company, product])
        await db.flush()
        db.add(contact)
        await db.flush()
        deal = Deal(id=str(uuid4()), organization_id=org.id, title="Sale", assigned_to=user.id,
                    company_id=company.id, contact_id=contact.id, stage="Qualification", amount=0)
        db.add(deal)
        await db.commit()
    try:
        yield sessions, org, user, company, contact, product, deal
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_win_persists_one_quote_and_immutable_items(sales_database):
    sessions, org, user, _, _, product, deal = sales_database
    async with sessions() as db:
        await DealService().add_deal_product(db, deal_id=deal.id, product_id=product.id,
            quantity=2, unit_price=100, custom_name=None, organization_id=org.id,
            discount_percent=10, tax_percent=18)

    async def win():
        async with sessions() as db:
            return await DealService().mark_deal_won(db, deal.id, 999999,
                organization_id=org.id, actor_id=user.id)

    first, second = await asyncio.gather(win(), win())
    assert first["quote_id"] == second["quote_id"]
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Quote).where(
            Quote.automatic_deal_id == deal.id)) == 1
        quote = await db.get(Quote, first["quote_id"])
        assert quote.total_amount == Decimal("212.40")
        assert quote.status == "Draft"
        assert quote.currency == "INR"
        persisted_deal = await db.get(Deal, deal.id)
        assert persisted_deal.stage == "Closed Won"
        assert Decimal(str(persisted_deal.amount)) == Decimal("212.40")
        item = await db.scalar(select(QuoteItem).where(QuoteItem.quote_id == quote.id))
        assert item.product_name == "Service"
        assert item.total == Decimal("212.40")
        catalog = await db.get(Product, product.id)
        catalog.price = 999
        await db.commit()
    async with sessions() as db:
        response = await QuoteService().get_quote(db, quote_id=first["quote_id"], organization_id=org.id)
        assert response["items"][0]["unit_price"] == Decimal("100.00")
        with pytest.raises(APIException, match="cannot be changed"):
            await DealService().add_deal_product(db, deal_id=deal.id, product_id=product.id,
                quantity=3, unit_price=1, custom_name=None, organization_id=org.id)


@pytest.mark.asyncio
async def test_failed_win_rolls_back_stage(sales_database):
    sessions, org, user, _, _, _, deal = sales_database
    async with sessions() as db:
        with pytest.raises(APIException, match="Add products"):
            await DealService().mark_deal_won(db, deal.id, None,
                organization_id=org.id, actor_id=user.id)
    async with sessions() as db:
        assert (await db.get(Deal, deal.id)).stage == "Qualification"
        assert await db.scalar(select(func.count()).select_from(Quote).where(
            Quote.automatic_deal_id == deal.id)) == 0


@pytest.mark.asyncio
async def test_foreign_deal_and_product_are_rejected(sales_database):
    sessions, org, user, _, _, product, deal = sales_database
    async with sessions() as db:
        with pytest.raises(NotFoundError):
            await DealService().mark_deal_won(db, deal.id, None,
                organization_id=str(uuid4()), actor_id=user.id)
        with pytest.raises(NotFoundError):
            await DealService().add_deal_product(db, deal_id=deal.id, product_id=str(uuid4()),
                quantity=1, unit_price=100, custom_name=None, organization_id=org.id)
        assert await db.get(Product, product.id) is not None


@pytest.mark.asyncio
async def test_concurrent_lead_conversion_reuses_real_customer_and_deal(sales_database):
    sessions, org, user, company, contact, _, _ = sales_database
    lead_id = str(uuid4())
    async with sessions() as db:
        db.add(Lead(id=lead_id, organization_id=org.id, title="Qualified sale",
                    company=company.name, contact_name=contact.name, email=contact.email,
                    status="Qualified", is_archived=False))
        await db.commit()

    async def convert():
        async with sessions() as db:
            return await LeadService().convert_lead(db, lead_id, LeadConvertRequest(), user)

    first, second = await asyncio.gather(convert(), convert())
    assert first == second
    assert first["company_id"] == company.id
    assert first["contact_id"] == contact.id
    async with sessions() as db:
        lead = await db.get(Lead, lead_id)
        assert lead.status == "Converted"
        assert lead.converted_deal_id == first["deal_id"]
        assert await db.get(Deal, first["deal_id"]) is not None


async def prepare_customer_acceptance(sales_database, *, billing=True):
    """Set up a sent quote; outbound email is deliberately outside these DB tests."""
    sessions, org, user, _, contact, product, deal = sales_database
    async with sessions() as db:
        if billing:
            db.add(ContactAddress(contact_id=contact.id, street="Test billing street", country="IN"))
            await db.commit()
        await DealService().add_deal_product(db, deal_id=deal.id, product_id=product.id,
            quantity=2, unit_price=100, custom_name=None, organization_id=org.id)
        won = await DealService().mark_deal_won(db, deal.id, None,
            organization_id=org.id, actor_id=user.id)
        quote = await db.get(Quote, won["quote_id"])
        await QuoteService().send_quote(db, quote_id=won["quote_id"], organization_id=org.id,
            recipient_email=contact.email)
        token = secrets.token_urlsafe(32)
        quote.public_token_hash = hashlib.sha256(token.encode()).hexdigest()
        quote.sent_at = datetime.now(UTC)
        quote.status = "Sent"
        await db.commit()
    return token, won["quote_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["Sent", "Failed", "Unknown"])
async def test_durable_quote_delivery_and_customer_acceptance(sales_database, monkeypatch, outcome):
    sessions, org, user, _, contact, product, deal = sales_database
    monkeypatch.setattr(settings, "BREVO_API_KEY", secrets.token_urlsafe(32))
    storage = Mock(return_value="test-quote-storage-key")
    monkeypatch.setattr("app.services.quote_delivery_service.s3_service.upload_file", storage)
    monkeypatch.setattr("app.services.quote_delivery_service.s3_service.generate_presigned_url",
                        Mock(return_value="https://storage.example.test/quote.pdf"))
    sender = Mock(return_value="test-provider-receipt")
    if outcome == "Failed":
        storage.side_effect = RuntimeError("Storage unavailable")
    if outcome == "Unknown":
        sender.side_effect = EmailDeliveryUnknownError("Timeout")
    monkeypatch.setattr("app.services.quote_delivery_service.send_tracked_email", sender)
    async with sessions() as db:
        db.add(ContactAddress(contact_id=contact.id, street="Test billing street", country="IN"))
        await db.commit()
        await DealService().add_deal_product(db, deal_id=deal.id, product_id=product.id,
            quantity=2, unit_price=100, custom_name=None, organization_id=org.id)
        won = await DealService().mark_deal_won(db, deal.id, None, organization_id=org.id, actor_id=user.id)
        first = await QuoteService().send_quote(db, quote_id=won["quote_id"], organization_id=org.id,
                                              recipient_email=contact.email)
        second = await QuoteService().send_quote(db, quote_id=won["quote_id"], organization_id=org.id,
                                               recipient_email=contact.email)
        assert first["status"] == second["status"] == "Pending"
    # Two competing workers must only claim/send this queued quote once.
    await asyncio.gather(QuoteDeliveryService().deliver_one(sessions), QuoteDeliveryService().deliver_one(sessions))
    async with sessions() as db:
        quote = await db.get(Quote, won["quote_id"])
        assert quote.delivery_status == outcome
        assert quote.delivery_attempts == 1
        if outcome == "Sent":
            sender.assert_called_once()
            assert quote.sent_at and quote.provider_message_id == "test-provider-receipt"
            token = acceptance_token(quote.id, quote.delivery_id)
            response = await QuoteService().public_quote(db, token=token)
            assert response["status"] == "Sent"
            result = await QuoteService().accept_public_quote(db, token=token)
            assert (await db.get(Invoice, result["invoice_id"])).status == "Pending"
        else:
            assert quote.sent_at is None and quote.status == "Draft"
            if outcome == "Failed":
                sender.assert_not_called()
            else:
                with pytest.raises(APIException, match="reconciliation"):
                    await QuoteService().send_quote(db, quote_id=quote.id, organization_id=org.id,
                                                   recipient_email=contact.email)


@pytest.mark.asyncio
async def test_concurrent_acceptance_creates_one_invoice(sales_database):
    token, quote_id = await prepare_customer_acceptance(sales_database)
    sessions, org, _, _, _, product, _ = sales_database
    async def accept():
        async with sessions() as db:
            return await QuoteService().accept_public_quote(db, token=token)
    first, second = await asyncio.gather(accept(), accept())
    assert first == second
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Invoice).where(Invoice.quote_id == quote_id)) == 1
        invoice = await db.get(Invoice, first["invoice_id"])
        assert invoice.organization_id == org.id
        assert invoice.amount == Decimal("200.00")
        assert invoice.paid_amount == 0
        assert invoice.status == "Pending"
        assert invoice.invoice_number.endswith("-000001")
        assert invoice.billing_snapshot["street"] == "Test billing street"
        items = list((await db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id))).all())
        assert len(items) == 1
        assert items[0].description == product.name
        assert items[0].unit_price == Decimal("100.00")
        quote = await db.get(Quote, quote_id)
        assert quote.status == "Accepted"
        assert quote.accepted_at and quote.approved_at


@pytest.mark.asyncio
async def test_failed_invoice_creation_rolls_back_customer_acceptance(sales_database):
    token, quote_id = await prepare_customer_acceptance(sales_database, billing=False)
    sessions, *_ = sales_database
    async with sessions() as db:
        with pytest.raises(APIException, match="billing"):
            await QuoteService().accept_public_quote(db, token=token)
    async with sessions() as db:
        quote = await db.get(Quote, quote_id)
        assert quote.status == "Sent"
        assert quote.accepted_at is None
        assert await db.scalar(select(func.count()).select_from(Invoice).where(Invoice.quote_id == quote_id)) == 0


async def prepare_payment_webhook(sales_database, monkeypatch, *, amount=20000, organization_id=None):
    """Generate signed test-provider data; this is not a live Stripe payment."""
    token, _ = await prepare_customer_acceptance(sales_database)
    sessions, org, *_ = sales_database
    session_id = f"cs_test_{uuid4().hex}"
    async with sessions() as db:
        acceptance = await QuoteService().accept_public_quote(db, token=token)
        invoice = await db.get(Invoice, acceptance["invoice_id"])
        invoice.stripe_checkout_session_id = session_id
        await db.commit()
    payload = json.dumps({"id": f"evt_{uuid4().hex}", "object": "event",
        "type": "checkout.session.completed", "data": {"object": {
            "id": session_id, "object": "checkout.session", "mode": "payment",
            "payment_status": "paid", "amount_total": amount, "currency": "inr",
            "payment_intent": f"pi_{uuid4().hex}",
            "metadata": {"invoice_id": invoice.id, "organization_id": organization_id or org.id},
        }}}).encode()
    secret = secrets.token_urlsafe(32)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", secret)
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    return invoice.id, payload, f"t={timestamp},v1={digest}"


@pytest.mark.asyncio
async def test_signed_concurrent_webhooks_create_one_payment(sales_database, monkeypatch):
    invoice_id, payload, signature = await prepare_payment_webhook(sales_database, monkeypatch)
    sessions, *_ = sales_database
    async def fulfill():
        async with sessions() as db:
            return await InvoicePaymentService().webhook(db, payload=payload, signature=signature)
    assert await asyncio.gather(fulfill(), fulfill()) == [{"received": True}, {"received": True}]
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.status == "Paid"
        assert invoice.paid_amount == invoice.amount == Decimal("200.00")
        payments = list((await db.scalars(select(Payment).where(Payment.invoice_id == invoice_id))).all())
        assert len(payments) == 1
        assert payments[0].amount == Decimal("200.00")
        assert payments[0].organization_id == invoice.organization_id


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["signature", "amount", "organization"])
async def test_invalid_payment_does_not_mark_invoice_paid(sales_database, monkeypatch, tamper):
    invoice_id, payload, signature = await prepare_payment_webhook(sales_database, monkeypatch,
        amount=1 if tamper == "amount" else 20000,
        organization_id=str(uuid4()) if tamper == "organization" else None)
    sessions, *_ = sales_database
    async with sessions() as db:
        with pytest.raises(APIException):
            await InvoicePaymentService().webhook(db, payload=payload,
                signature="invalid" if tamper == "signature" else signature)
    async with sessions() as db:
        invoice = await db.get(Invoice, invoice_id)
        assert invoice.status == "Pending"
        assert invoice.paid_amount == 0
        assert await db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)) == 0
