from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Organization
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


@pytest.mark.asyncio
async def test_get_organization_by_id_not_found():
    repo: Any = OrganizationRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_organization_by_id(db, "missing-org")


@pytest.mark.asyncio
async def test_get_organization_falls_back_to_default(monkeypatch):
    org = _make_org()
    repo: Any = OrganizationRepository()
    repo.get_first = AsyncMock(return_value=None)
    repo.get_or_create_default = AsyncMock(return_value=org)
    repo.count_members = AsyncMock(return_value=5)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_organization(db, None)

    assert result["members_count"] == 5
    assert result["plan"] == "Enterprise"


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
async def test_remove_member_missing_user_returns_message():
    repo: Any = OrganizationRepository()
    repo.get_user_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.remove_member(db, "ghost-user")

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_usage_reports_limits():
    org = _make_org(plan="Business")
    sub = type("S", (), {"storage_used_gb": 2.0, "status": "active", "plan_id": None})()
    repo: Any = OrganizationRepository()
    repo.get_first = AsyncMock(return_value=org)
    repo.get_subscription = AsyncMock(return_value=None)
    repo.get_plan_by_slug = AsyncMock(return_value=None)
    repo.create_subscription = AsyncMock(return_value=sub)
    repo.count_members = AsyncMock(return_value=4)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_usage(db, None)

    assert result["users_used"] == 4
    assert result["users_limit"] == DEFAULT_PLANS["business"]["max_users"]
    assert result["ai_credits_limit"] == DEFAULT_PLANS["business"]["ai_credits"]


def test_org_to_dict_applies_defaults():
    org = _make_org()
    assert org_to_dict(org)["timezone"] == "Asia/Kolkata"
    assert org_to_dict(org)["currency"] == "INR"
    assert org_to_dict(org)["members_count"] == 1
