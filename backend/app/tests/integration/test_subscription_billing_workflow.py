"""Real PostgreSQL subscription transactions with a fake provider boundary.

These tests prove local state transitions, not live Stripe delivery or checkout.
The isolated runner forbids importing the installed Stripe SDK.
"""

import asyncio
import copy
import json
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.models import (
    AuditLog,
    Organization,
    OrganizationSubscription,
    ProcessedWebhookEvent,
    SubscriptionPlan,
)
from app.services.subscription_billing_service import SubscriptionBillingService
from app.services.subscription_stripe_provider import SCOPE, SubscriptionStripeProvider
from app.tests.integration.test_sales_quote_workflow import sales_database as sales_database


class FakeSubscriptionProvider:
    def __init__(self):
        self.sessions: dict[str, dict[str, Any]] = {}
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.prices = {}
        self.create_customer = AsyncMock(
            side_effect=lambda **data: {"id": f"cus_{data['organization_id']}"}
        )
        self.ensure_price = AsyncMock(side_effect=self._price)
        self.create_checkout = AsyncMock(side_effect=self._checkout)
        self.retrieve_checkout = AsyncMock(
            side_effect=lambda identity: copy.deepcopy(self.sessions[identity])
        )
        self.retrieve_subscription = AsyncMock(
            side_effect=lambda identity: copy.deepcopy(self.subscriptions[identity])
        )
        self.create_portal = AsyncMock(
            return_value={"url": "https://billing.example.com/fake-portal"}
        )
        self.set_auto_renew = AsyncMock(side_effect=self._renew)
        self.construct_event = AsyncMock(side_effect=self._event)

    def _price(self, *, plan_slug, name, amount_minor):
        price = {
            "id": f"price_{plan_slug}",
            "currency": "inr",
            "unit_amount": amount_minor,
            "recurring": {"interval": "month", "interval_count": 1},
            "metadata": {"scope": SCOPE, "plan_slug": plan_slug},
        }
        self.prices[price["id"]] = price
        return copy.deepcopy(price)

    def _checkout(self, **data):
        identity = f"cs_{data['operation_id'][:24]}"
        self.sessions.setdefault(
            identity,
            {
                "id": identity,
                "url": f"https://checkout.example.com/{identity}",
                "mode": "subscription",
                "status": "open",
                "payment_status": "unpaid",
                "client_reference_id": data["organization_id"],
                "customer": data["customer_id"],
                "metadata": {
                    key: data[key] for key in ("organization_id", "operation_id", "plan_slug")
                }
                | {"scope": SCOPE},
            },
        )
        return copy.deepcopy(self.sessions[identity])

    def _renew(self, subscription_id, *, auto_renew):
        self.subscriptions[subscription_id]["cancel_at_period_end"] = not auto_renew
        return copy.deepcopy(self.subscriptions[subscription_id])

    def _event(self, payload_bytes, sig_header):
        if sig_header != "fake-valid":
            raise APIException(message="Invalid webhook signature", status_code=400)
        return json.loads(payload_bytes)

    def complete(self, session_id):
        session = self.sessions[session_id]
        remote_id = f"sub_{session_id[3:]}"
        session.update(status="complete", payment_status="paid", subscription=remote_id)
        price = self.prices[f"price_{session['metadata']['plan_slug']}"]
        self.subscriptions[remote_id] = {
            "id": remote_id,
            "status": "active",
            "customer": session["customer"],
            "metadata": copy.deepcopy(session["metadata"]),
            "cancel_at_period_end": False,
            "items": {
                "data": [
                    {
                        "id": "si_existing",
                        "quantity": 1,
                        "price": copy.deepcopy(price),
                        "current_period_start": 1788220800,
                        "current_period_end": 1790812800,
                    }
                ]
            },
            "latest_invoice": {
                "id": f"in_{remote_id}",
                "status": "paid",
                "subscription": remote_id,
                "customer": session["customer"],
                "currency": "inr",
                "lines": {"data": [{"price": price["id"], "amount": price["unit_amount"]}]},
            },
        }
        return remote_id


@pytest_asyncio.fixture
async def billing_context(sales_database):
    sessions, org, user, *_ = sales_database
    async with sessions() as db:
        persisted_org = await db.get(Organization, org.id)
        persisted_org.plan, persisted_org.max_users = "Free", 3
        plan = SubscriptionPlan(
            id=str(uuid4()),
            slug=f"professional-{uuid4().hex}",
            name="Professional",
            price_monthly=2999,
            max_users=50,
            max_storage_gb=100,
            ai_credits=5000,
            is_active=True,
        )
        upgrade = SubscriptionPlan(
            id=str(uuid4()),
            slug=f"enterprise-{uuid4().hex}",
            name="Enterprise",
            price_monthly=5999,
            max_users=100,
            max_storage_gb=500,
            ai_credits=10000,
            is_active=True,
        )
        db.add_all([plan, upgrade])
        await db.commit()
    provider = FakeSubscriptionProvider()
    return (
        sessions,
        org,
        user,
        plan,
        upgrade,
        provider,
        SubscriptionBillingService(provider=cast(SubscriptionStripeProvider, provider)),
    )


async def checkout(context, *, key="initial-request", plan=None):
    sessions, org, user, initial, _, _, service = context
    async with sessions() as db:
        return await service.create_checkout(
            db,
            plan_slug=(plan or initial).slug,
            org_id=org.id,
            current_user=user,
            idempotency_key=key,
        )


async def webhook(context, event):
    sessions, *_, service = context
    async with sessions() as db:
        return await service.handle_webhook(
            db, payload_bytes=json.dumps(event).encode(), sig_header="fake-valid"
        )


def event(event_type, obj, *, event_id=None):
    return {
        "id": event_id or f"evt_{uuid4().hex}",
        "type": event_type,
        "data": {"object": copy.deepcopy(obj)},
    }


async def activate(context):
    response = await checkout(context)
    provider = context[-2]
    remote_id = provider.complete(response["session_id"])
    await webhook(
        context, event("checkout.session.completed", provider.sessions[response["session_id"]])
    )
    return response, remote_id


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_checkout_retries_keep_one_local_subscription_and_remote_session(
    billing_context, existing
):
    sessions, org, _, _, _, provider, _ = billing_context
    original_id = None
    if existing:
        original_id = str(uuid4())
        async with sessions() as db:
            db.add(
                OrganizationSubscription(
                    id=original_id,
                    organization_id=org.id,
                    status="active",
                    amount=0,
                    max_users=3,
                    ai_credits=50,
                    storage_limit_gb=5,
                )
            )
            await db.commit()
    first, second = await asyncio.gather(checkout(billing_context), checkout(billing_context))
    assert first == second
    assert await checkout(billing_context, key="another-click") == first
    assert len(provider.sessions) == 1
    async with sessions() as db:
        sub = (
            await db.scalars(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org.id
                )
            )
        ).one()
        assert sub.checkout_session_id == first["session_id"]
        if original_id:
            assert sub.id == original_id
        assert (await db.get(Organization, org.id)).plan == "Free"
        assert sub.amount == 0


@pytest.mark.asyncio
async def test_unknown_remote_outcome_retries_same_provider_operation(billing_context):
    provider = billing_context[-2]
    attempts = 0

    def timeout_once(**data):
        nonlocal attempts
        result = provider._checkout(**data)
        attempts += 1
        if attempts == 1:
            raise APIException(message="Fake provider timeout", status_code=502)
        return result

    provider.create_checkout.side_effect = timeout_once
    with pytest.raises(APIException):
        await checkout(billing_context)
    result = await checkout(billing_context)
    assert len(provider.sessions) == 1
    assert result["session_id"] in provider.sessions
    assert (
        provider.create_checkout.await_args_list[0] == provider.create_checkout.await_args_list[1]
    )


@pytest.mark.asyncio
async def test_verification_does_not_grant_entitlements_before_webhook(billing_context):
    sessions, org, user, plan, _, provider, service = billing_context
    response = await checkout(billing_context)
    provider.complete(response["session_id"])
    async with sessions() as db:
        verified = await service.verify_checkout(
            db, session_id=response["session_id"], plan_slug=plan.slug, current_user=user
        )
        assert verified["verified"] is True
        assert verified["db_synced"] is False
        assert (await db.get(Organization, org.id)).plan == "Free"
    await webhook(
        billing_context,
        event("checkout.session.completed", provider.sessions[response["session_id"]]),
    )
    async with sessions() as db:
        result = await service.verify_checkout(
            db, session_id=response["session_id"], plan_slug=plan.slug, current_user=user
        )
        assert result["db_synced"] is True
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_webhook_replay_concurrently_commits_entitlements_and_event_once(billing_context):
    sessions, org, _, plan, _, provider, _ = billing_context
    response = await checkout(billing_context)
    provider.complete(response["session_id"])
    signed = event("checkout.session.completed", provider.sessions[response["session_id"]])
    await asyncio.gather(webhook(billing_context, signed), webhook(billing_context, signed))
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(ProcessedWebhookEvent)
                .where(ProcessedWebhookEvent.event_id == signed["id"])
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.organization_id == org.id, AuditLog.action == "subscription.webhook"
                )
            )
            == 1
        )
        assert (await db.get(Organization, org.id)).max_users == plan.max_users


@pytest.mark.asyncio
async def test_webhook_failure_rolls_back_entitlements_and_replay_marker(
    billing_context, monkeypatch
):
    sessions, org, _, _, _, provider, service = billing_context
    response = await checkout(billing_context)
    provider.complete(response["session_id"])
    signed = event("checkout.session.completed", provider.sessions[response["session_id"]])
    original = service.repository.record_processed_webhook_event
    monkeypatch.setattr(
        service.repository,
        "record_processed_webhook_event",
        AsyncMock(side_effect=RuntimeError("event persistence failed")),
    )
    with pytest.raises(RuntimeError):
        await webhook(billing_context, signed)
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Free"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(ProcessedWebhookEvent)
                .where(ProcessedWebhookEvent.event_id == signed["id"])
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.organization_id == org.id, AuditLog.action == "subscription.webhook"
                )
            )
            == 0
        )
    monkeypatch.setattr(service.repository, "record_processed_webhook_event", original)
    assert (await webhook(billing_context, signed))["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "remote_status,invoice_status",
    [("past_due", "open"), ("active", "open"), ("incomplete", "uncollectible")],
)
async def test_unpaid_subscription_never_grants_paid_plan(
    billing_context, remote_status, invoice_status
):
    sessions, org, _, _, _, provider, _ = billing_context
    response = await checkout(billing_context)
    remote_id = provider.complete(response["session_id"])
    provider.subscriptions[remote_id]["status"] = remote_status
    provider.subscriptions[remote_id]["latest_invoice"]["status"] = invoice_status
    await webhook(
        billing_context,
        event("invoice.payment_failed", provider.subscriptions[remote_id]["latest_invoice"]),
    )
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Free"
        sub = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org.id
            )
        )
        assert sub.amount == 0


@pytest.mark.asyncio
async def test_existing_subscription_upgrade_uses_portal_and_canonical_state_for_old_event(
    billing_context,
):
    sessions, org, _, _, upgrade, provider, _ = billing_context
    _, remote_id = await activate(billing_context)
    old_snapshot = copy.deepcopy(provider.subscriptions[remote_id])
    portal = await checkout(billing_context, key="upgrade", plan=upgrade)
    assert await checkout(billing_context, key="upgrade", plan=upgrade) == portal
    assert provider.create_portal.await_args_list[0] == provider.create_portal.await_args_list[1]
    assert portal["session_id"] is None
    assert provider.create_portal.await_args.kwargs["subscription_id"] == remote_id
    assert provider.create_checkout.await_count == 1
    remote = provider.subscriptions[remote_id]
    price = provider.prices[f"price_{upgrade.slug}"]
    remote["items"]["data"][0]["price"] = copy.deepcopy(price)
    remote["latest_invoice"].update(
        id=f"in_upgrade_{uuid4().hex}",
        lines={"data": [{"price": price["id"], "amount": price["unit_amount"]}]},
    )
    await webhook(billing_context, event("invoice.paid", remote["latest_invoice"]))
    old_snapshot["status"] = "canceled"
    await webhook(billing_context, event("customer.subscription.deleted", old_snapshot))
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Enterprise"
        sub = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org.id
            )
        )
        assert sub.subscription_id == remote_id
        assert sub.status == "active"
        assert sub.max_users == upgrade.max_users


@pytest.mark.asyncio
async def test_tenant_mismatch_and_foreign_checkout_rejected(billing_context):
    sessions, _, user, plan, _, provider, service = billing_context
    async with sessions() as db:
        with pytest.raises(ForbiddenError):
            await service.create_checkout(
                db,
                plan_slug=plan.slug,
                org_id=str(uuid4()),
                current_user=user,
                idempotency_key="key",
            )
    provider.create_checkout.assert_not_awaited()
    await checkout(billing_context)
    async with sessions() as db:
        with pytest.raises(NotFoundError):
            await service.verify_checkout(
                db, session_id="cs_foreign", plan_slug=plan.slug, current_user=user
            )


@pytest.mark.asyncio
async def test_unknown_plan_does_not_start_provider_checkout(billing_context):
    sessions, org, user, _, _, provider, service = billing_context
    async with sessions() as db:
        with pytest.raises(APIException) as exc:
            await service.create_checkout(
                db,
                plan_slug="unknown-nonexistent-plan",
                org_id=org.id,
                current_user=user,
                idempotency_key="key",
            )
    assert exc.value.code == "UNKNOWN_PLAN"
    provider.create_customer.assert_not_awaited()


@pytest.mark.asyncio
async def test_renewal_changes_same_subscription_without_downgrading_plan(billing_context):
    sessions, org, user, _, _, provider, service = billing_context
    _, remote_id = await activate(billing_context)
    for auto_renew in (False, True):
        async with sessions() as db:
            await service.set_auto_renew(db, current_user=user, auto_renew=auto_renew)
        assert provider.set_auto_renew.await_args.args == (remote_id,)
        async with sessions() as db:
            sub = await db.scalar(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org.id
                )
            )
            assert sub.auto_renew is auto_renew
            assert sub.status == "active"
            assert (await db.get(Organization, org.id)).plan == "Professional"


@pytest.mark.asyncio
async def test_missing_subscription_config_does_not_break_manual_invoice_payments(
    billing_context, sales_database, monkeypatch
):
    from app.tests.integration.test_manual_invoice_workflow import accepted_invoice, pay

    sessions, org, user, plan, *_ = billing_context
    service = SubscriptionBillingService(provider=SubscriptionStripeProvider())
    async with sessions() as db:
        with pytest.raises(APIException) as exc:
            await service.create_checkout(
                db,
                plan_slug=plan.slug,
                org_id=org.id,
                current_user=user,
                idempotency_key="missing-config",
            )
        assert exc.value.status_code == 503
    invoice_id = await accepted_invoice(sales_database, monkeypatch)
    payment = await pay(sales_database, invoice_id, "100.00")
    assert payment["status"] == "Succeeded"
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Free"


@pytest.mark.asyncio
async def test_expired_checkout_requires_new_key_without_duplicate_subscription(billing_context):
    response = await checkout(billing_context)
    provider = billing_context[-2]
    provider.sessions[response["session_id"]]["status"] = "expired"
    with pytest.raises(ConflictError, match="expired"):
        await checkout(billing_context)
    renewed = await checkout(billing_context, key="renewed-checkout")
    assert renewed["session_id"] != response["session_id"]
    sessions, org, *_ = billing_context
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(OrganizationSubscription)
                .where(OrganizationSubscription.organization_id == org.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_webhook_wrong_customer_rolls_back_without_consuming_event(billing_context):
    response = await checkout(billing_context)
    provider = billing_context[-2]
    remote_id = provider.complete(response["session_id"])
    provider.subscriptions[remote_id]["customer"] = "cus_foreign"
    signed = event("checkout.session.completed", provider.sessions[response["session_id"]])
    with pytest.raises(ConflictError, match="customer"):
        await webhook(billing_context, signed)
    sessions, org, *_ = billing_context
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Free"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(ProcessedWebhookEvent)
                .where(ProcessedWebhookEvent.event_id == signed["id"])
            )
            == 0
        )


@pytest.mark.asyncio
async def test_http_subscription_authorization_and_webhook_sync(billing_context, monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.deps import get_current_user
    from app.api.v1.routers import organizations
    from app.core.errors import register_exception_handlers
    from app.db.session import get_db
    from app.services.auth_service import auth_service

    sessions, org, user, plan, _, provider, service = billing_context
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(organizations.router, prefix="/api/v1/organizations")

    async def database_override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    monkeypatch.setattr(organizations, "subscription_billing_service", service)
    permission = AsyncMock(return_value=[])
    monkeypatch.setattr(auth_service, "get_user_permissions", permission)
    base = "/api/v1/organizations/subscription"
    payload = {"plan_slug": plan.slug}
    headers = {"Idempotency-Key": str(uuid4())}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(f"{base}/checkout", json=payload, headers=headers)
        ).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert (
            await client.post(f"{base}/checkout", json=payload, headers=headers)
        ).status_code == 403
        permission.return_value = ["organization:billing"]
        assert (
            await client.post(
                f"{base}/checkout", json=payload | {"org_id": str(uuid4())}, headers=headers
            )
        ).status_code == 403
        created = await client.post(f"{base}/checkout", json=payload, headers=headers)
        assert created.status_code == 200, created.text
        session_id = created.json()["session_id"]
        provider.complete(session_id)
        verified = await client.get(
            f"{base}/checkout/verify", params={"session_id": session_id, "plan_slug": plan.slug}
        )
        assert verified.status_code == 200
        assert verified.json()["verified"] is True
        assert verified.json()["db_synced"] is False
        assert (
            await client.get(
                f"{base}/checkout/verify", params={"session_id": session_id, "org_id": str(uuid4())}
            )
        ).status_code == 403
        signed = event("checkout.session.completed", provider.sessions[session_id])
        # Webhooks authenticate with provider evidence, not a browser session.
        app.dependency_overrides.pop(get_current_user)
        assert (await client.post(f"{base}/webhook", content=json.dumps(signed))).status_code == 400
        delivered = await client.post(
            f"{base}/webhook",
            content=json.dumps(signed),
            headers={"Stripe-Signature": "fake-valid"},
        )
        assert delivered.status_code == 200, delivered.text
        app.dependency_overrides[get_current_user] = lambda: user
        verified = await client.get(
            f"{base}/checkout/verify", params={"session_id": session_id, "plan_slug": plan.slug}
        )
        assert verified.json()["db_synced"] is True
    async with sessions() as db:
        assert (await db.get(Organization, org.id)).plan == "Professional"


@pytest.mark.asyncio
async def test_distinct_events_for_same_paid_invoice_preserve_spent_ai_credits(billing_context):
    sessions, org, _, _, _, provider, _ = billing_context
    _, remote_id = await activate(billing_context)
    async with sessions() as db:
        sub = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org.id
            )
        )
        sub.ai_credits = 4321
        await db.commit()
    remote = provider.subscriptions[remote_id]
    await webhook(billing_context, event("invoice.paid", remote["latest_invoice"]))
    await webhook(billing_context, event("customer.subscription.updated", remote))
    async with sessions() as db:
        sub = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org.id
            )
        )
        assert sub.ai_credits == 4321
        assert sub.status == "active"


@pytest.mark.asyncio
async def test_pending_upgrade_preserves_previous_paid_plan_and_active_status(billing_context):
    sessions, org, _, _, upgrade, provider, _ = billing_context
    _, remote_id = await activate(billing_context)
    await checkout(billing_context, key="pending-upgrade", plan=upgrade)
    remote = provider.subscriptions[remote_id]
    remote["pending_update"] = {"subscription_items": [{"price": f"price_{upgrade.slug}"}]}
    remote["latest_invoice"]["status"] = "open"
    await webhook(billing_context, event("customer.subscription.updated", remote))
    async with sessions() as db:
        sub = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org.id
            )
        )
        assert (await db.get(Organization, org.id)).plan == "Professional"
        assert sub.status == "active"
        assert sub.amount == 2999
