"""Subscription restoration must retain manual-invoice and entitlement safeguards."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import organizations
from app.core.errors import APIException, register_exception_handlers
from app.models import Organization, OrganizationSubscription, SubscriptionPlan, User
from app.repositories.auth_repository import AuthRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.crm_schemas import OrganizationUpdate
from app.services.organization_service import OrganizationDomainService


@pytest.mark.asyncio
@pytest.mark.parametrize("plan", ["free", "professional", "enterprise", "unknown"])
async def test_direct_upgrade_requires_checkout_without_database_access(plan):
    repo = AsyncMock(spec=OrganizationRepository)
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException, match="[Cc]heckout") as exc:
        await OrganizationDomainService(repo).upgrade_plan(db, plan)
    assert exc.value.status_code == 400
    assert not repo.mock_calls
    assert not db.mock_calls


@pytest.mark.asyncio
async def test_subscription_provider_routes_present_and_direct_upgrade_blocked():
    app = FastAPI()
    app.include_router(organizations.router, prefix="/organizations")
    register_exception_handlers(app)
    db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[organizations.get_db] = lambda: db
    for route in organizations.router.routes:
        for dependency in route.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: None
    for method, path in (
        ("POST", "/subscription/checkout"),
        ("GET", "/subscription/checkout/verify"),
        ("POST", "/subscription/webhook"),
    ):
        assert method.lower() in app.openapi()["paths"]["/organizations" + path]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/organizations/subscription/upgrade?plan_slug=enterprise")
    assert response.status_code == 400
    assert "checkout" in response.json()["message"].lower()
    assert not db.mock_calls


@pytest.mark.asyncio
async def test_existing_subscription_and_usage_preserve_entitlements():
    org = Organization(id="org-1", plan="Professional", max_users=50)
    sub = OrganizationSubscription(
        id="sub-1",
        organization_id=org.id,
        plan_id="plan-1",
        amount=2999,
        status="active",
        auto_renew=True,
        payment_provider="Stripe",
        customer_id="historical-customer",
        subscription_id="historical-subscription",
        max_users=50,
        storage_limit_gb=100,
        storage_used_gb=7,
        ai_credits=5000,
    )
    before = {column.key: getattr(sub, column.key) for column in sub.__table__.columns}
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_by_id.return_value = org
    repo.get_subscription.return_value = sub
    repo.get_plan_by_id.return_value = SubscriptionPlan(
        id="plan-1",
        name="Professional",
        slug="professional",
        price_monthly=2999,
        max_users=50,
        max_storage_gb=100,
        ai_credits=5000,
        features="Reports",
    )
    repo.count_members.return_value = 4
    service = OrganizationDomainService(repo)
    db = AsyncMock(spec=AsyncSession)
    actor = User(id="user-1", organization_id=org.id)
    result = await service.get_subscription(db, actor)
    usage = await service.get_usage(db, actor)
    assert result["plan_slug"] == "professional"
    assert result["max_users"] == usage["users_limit"] == 50
    assert result["ai_credits"] == usage["ai_credits_limit"] == 5000
    assert result["storage_limit_gb"] == usage["storage_gb_limit"] == 100
    assert before == {column.key: getattr(sub, column.key) for column in sub.__table__.columns}
    repo.create_subscription.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_subscriptions_have_no_provider():
    db = AsyncMock(spec=AsyncSession)
    plan = SubscriptionPlan(
        id="free-plan",
        slug="free",
        name="Free",
        price_monthly=0,
        currency="INR",
        billing_cycle="month",
        max_users=3,
        max_storage_gb=5,
        ai_credits=50,
    )
    sub = await AuthRepository().create_organization_subscription(
        db, organization_id="org-1", plan=plan
    )
    assert sub.payment_provider is None
    assert sub.max_users == 3
    assert sub.ai_credits == 50
    assert sub.plan_id == "free-plan"
    assert sub.auto_renew is False
    column = OrganizationSubscription.__table__.c.payment_provider
    assert column.default is None
    assert column.server_default is None
    assert sub.checkout_session_id is None


@pytest.mark.asyncio
async def test_lazy_subscription_creation_has_no_provider_or_plan_upgrade():
    org = Organization(id="org-1", plan="Free", max_users=3)
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_subscription.return_value = None
    repo.get_by_id_for_update.return_value = org
    repo.get_subscription.side_effect = [None, None]
    repo.get_plan_by_slug.return_value = SubscriptionPlan(
        id="free-plan",
        slug="free",
        name="Free",
        price_monthly=0,
        currency="INR",
        billing_cycle="month",
        max_users=3,
        max_storage_gb=5,
        ai_credits=50,
        is_active=True,
    )
    repo.create_subscription.side_effect = OrganizationRepository().create_subscription
    db = AsyncMock(spec=AsyncSession)
    sub = await OrganizationDomainService(repo).get_or_create_subscription(db, org)
    assert sub.payment_provider is None
    assert sub.plan_id == "free-plan"
    assert sub.amount == 0
    assert org.plan == "Free"
    assert org.max_users == 3
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_lazy_subscription_creation_rechecks_after_organization_lock():
    org = Organization(id="org-1", plan="Free", max_users=3)
    existing = OrganizationSubscription(id="sub-existing", organization_id=org.id)
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_subscription.side_effect = [None, existing]
    repo.get_by_id_for_update.return_value = org
    db = AsyncMock(spec=AsyncSession)

    result = await OrganizationDomainService(repo).get_or_create_subscription(db, org)

    assert result is existing
    repo.get_by_id_for_update.assert_awaited_once_with(db, org.id)
    repo.create_subscription.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [{"plan": "Enterprise"}, {"max_users": 100}])
async def test_settings_cannot_escalate_entitlements(fields):
    org = Organization(id="org-1", plan="Free", max_users=3)
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_by_id.return_value = org
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as exc:
        await OrganizationDomainService(repo).update_organization_by_id(
            db, org.id, OrganizationUpdate(**fields), User(organization_id=org.id)
        )
    assert exc.value.status_code == 403
    assert org.plan == "Free"
    assert org.max_users == 3
    repo.create_audit_log.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_settings_allow_unchanged_entitlements():
    org = Organization(id="org-1", name="Old", plan="Free", max_users=3)
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_by_id.return_value = org
    repo.count_members.return_value = 1
    db = AsyncMock(spec=AsyncSession)
    result = await OrganizationDomainService(repo).update_organization_by_id(
        db,
        org.id,
        OrganizationUpdate(name="New", plan="Free", max_users=3),
        User(organization_id=org.id),
    )
    assert result["name"] == "New"
    assert result["plan"] == "Free"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,key",
    [
        ({"plan_slug": "Enterprise"}, "valid"),
        ({"plan_slug": "enterprise", "amount": 1}, "valid"),
        ({"plan_slug": "x" * 101}, "valid"),
        ({"plan_slug": "enterprise"}, "not-a-uuid"),
        ({"plan_slug": "enterprise"}, None),
    ],
)
async def test_checkout_boundary_rejects_invalid_requests(monkeypatch, payload, key):
    app = FastAPI()
    app.include_router(organizations.router, prefix="/organizations")
    app.dependency_overrides[organizations.get_db] = lambda: AsyncMock(spec=AsyncSession)
    app.dependency_overrides[organizations.get_current_user] = lambda: User(
        id="user", organization_id="org"
    )
    for route in organizations.router.routes:
        for dependency in route.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: None
    checkout = AsyncMock()
    monkeypatch.setattr(organizations.subscription_billing_service, "create_checkout", checkout)
    headers = {} if key is None else {"Idempotency-Key": str(uuid4()) if key == "valid" else key}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/organizations/subscription/checkout", json=payload, headers=headers
        )
    assert response.status_code == 422
    checkout.assert_not_awaited()
