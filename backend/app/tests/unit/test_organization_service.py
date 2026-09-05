from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.models import Organization, OrganizationSubscription, User
from app.repositories.organization_repository import OrganizationRepository
from app.services.organization_service import (
    DEFAULT_PLANS,
    OrganizationDomainService,
    org_to_dict,
)


def _make_org(**overrides) -> Organization:
    defaults = {
        "id": "org-1",
        "name": "Acme Inc",
        "slug": "acme",
        "domain": "acme.crm.com",
        "plan": "Enterprise",
        "max_users": 100,
        "status": "active",
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Organization(**defaults)


def _service_with(repo: OrganizationRepository) -> OrganizationDomainService:
    return OrganizationDomainService(repository=repo)


def _actor(organization_id: str = "org-1") -> User:
    return User(
        id="admin-1",
        email="admin@example.com",
        organization_id=organization_id,
    )


@pytest.mark.asyncio
async def test_get_organization_by_id_not_found():
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_organization_by_id(db, "missing-org", _actor())


@pytest.mark.asyncio
async def test_get_organization_uses_authenticated_organization():
    org = _make_org()
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=org)
    repo.count_members = AsyncMock(return_value=5)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_organization(db, _actor())

    assert result["members_count"] == 5
    assert result["plan"] == "Enterprise"


@pytest.mark.asyncio
async def test_get_current_organization_uses_authenticated_users_org():
    org = _make_org(id="org-current")
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=org)
    repo.count_members = AsyncMock(return_value=3)
    repo.get_first = AsyncMock()
    repo.get_or_create_default = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = User(
        id="user-1",
        name="Admin",
        email="admin@example.com",
        organization_id="org-current",
        is_active=True,
    )

    result = await service.get_current_organization(db, current_user)

    assert result["id"] == "org-current"
    assert result["members_count"] == 3
    repo.get_by_id.assert_awaited_once_with(db, "org-current")
    repo.get_first.assert_not_called()
    repo.get_or_create_default.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_organization_rejects_user_without_org():
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = User(
        id="user-1",
        name="Admin",
        email="admin@example.com",
        organization_id=None,
        is_active=True,
    )

    with pytest.raises(ForbiddenError, match="no current organization"):
        await service.get_current_organization(db, current_user)

    repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_organization_fails_when_assigned_org_is_missing():
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_first = AsyncMock()
    repo.get_or_create_default = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = User(
        id="user-1",
        name="Admin",
        email="admin@example.com",
        organization_id="missing-org",
        is_active=True,
    )

    with pytest.raises(NotFoundError, match="Current organization not found"):
        await service.get_current_organization(db, current_user)

    repo.get_first.assert_not_called()
    repo.get_or_create_default.assert_not_called()


@pytest.mark.asyncio
async def test_upgrade_plan_sets_subscription_metadata():
    org = _make_org()
    sub = type(
        "S",
        (),
        {"id": "sub-1", "plan_id": None, "amount": 0.0, "status": "active", "auto_renew": True},
    )()
    repo: Any = OrganizationRepository()
    repo.get_first = AsyncMock(return_value=org)
    repo.get_by_id = AsyncMock(return_value=org)
    repo.get_subscription = AsyncMock(return_value=None)
    repo.get_plan_by_slug = AsyncMock(return_value=None)
    repo.create_subscription = AsyncMock(return_value=sub)
    repo.create_audit_log = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.upgrade_plan(db, "professional")

    assert sub.amount == DEFAULT_PLANS["professional"]["price_monthly"]
    assert org.plan == "Professional"
    assert result["status"] == "success"
    repo.create_audit_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_subscription_plans_falls_back_to_defaults():
    repo: Any = OrganizationRepository()
    repo.list_active_plans = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    plans = await service.list_subscription_plans(db)

    assert len(plans) == 5
    assert plans[0]["slug"] == "free"


@pytest.mark.asyncio
async def test_get_subscription_does_not_fabricate_next_billing_date():
    org = _make_org()
    subscription = OrganizationSubscription(
        id="sub-1",
        organization_id=org.id,
        plan_id=None,
        status="active",
        billing_cycle="Monthly",
        amount=0.0,
        currency="INR",
        next_billing=None,
    )
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=org)
    repo.get_subscription = AsyncMock(return_value=subscription)
    repo.get_plan_by_slug = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_subscription(db, _actor())

    assert result["next_billing"] is None


@pytest.mark.asyncio
async def test_remove_member_missing_or_cross_tenant_user_is_not_found():
    repo: Any = OrganizationRepository()
    repo.get_user_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    actor = User(id="admin-1", organization_id="org-1")
    with pytest.raises(NotFoundError):
        await service.remove_member(db, "ghost-user", actor)

    repo.get_user_by_id.assert_awaited_once_with(db, user_id="ghost-user", organization_id="org-1")
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_usage_reports_limits():
    org = _make_org(plan="Business")
    sub = type("S", (), {"storage_used_gb": 2.0, "status": "active", "plan_id": None})()
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=org)
    repo.get_subscription = AsyncMock(return_value=None)
    repo.get_plan_by_slug = AsyncMock(return_value=None)
    repo.create_subscription = AsyncMock(return_value=sub)
    repo.count_members = AsyncMock(return_value=4)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_usage(db, _actor())

    assert result["users_used"] == 4
    assert result["users_limit"] == DEFAULT_PLANS["business"]["max_users"]
    assert result["ai_credits_limit"] == DEFAULT_PLANS["business"]["ai_credits"]


def test_org_to_dict_applies_defaults():
    org = _make_org()
    assert org_to_dict(org)["timezone"] == "Asia/Kolkata"
    assert org_to_dict(org)["currency"] == "INR"
    assert org_to_dict(org)["members_count"] == 1
