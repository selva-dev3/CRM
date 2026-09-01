from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.crm_schemas import CompanyCreate, CompanyUpdate
from app.services.company_service import CompanyService
from app.services.integration_service import integration_service


def _make_company(**overrides) -> Company:
    defaults = {
        "id": "cmp-1",
        "organization_id": "org-1",
        "name": "Acme Inc",
        "industry": "Software",
        "website": "acme.com",
        "employee_count": 250,
    }
    defaults.update(overrides)
    return Company(**defaults)


def _service_with(repo: CompanyRepository) -> CompanyService:
    return CompanyService(repository=repo)


@pytest.mark.asyncio
async def test_get_company_raises_not_found_when_missing():
    repo: Any = CompanyRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_company(db, "missing-company")


@pytest.mark.asyncio
async def test_create_company_serializes_domain_and_size(monkeypatch):
    company = _make_company()
    repo: Any = CompanyRepository()
    repo.create = AsyncMock(return_value=company)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.company_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = CompanyCreate(name="Acme Inc", size="250")
    result = await service.create_company(db, payload)

    assert result["id"] == "cmp-1"
    assert result["domain"] == "acme.com"
    assert result["size"] == "250"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_company_fires_company_created_event(monkeypatch):
    company = _make_company()
    repo: Any = CompanyRepository()
    repo.create = AsyncMock(return_value=company)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.services.company_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.create_company(db, CompanyCreate(name="Acme Inc"))

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "company.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["name"] == "Acme Inc"


@pytest.mark.asyncio
async def test_update_company_fires_company_updated_event(monkeypatch):
    company = _make_company()
    repo: Any = CompanyRepository()
    repo.get_by_id = AsyncMock(return_value=company)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_company(db, "cmp-1", CompanyUpdate(industry="Fintech"))

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "company.updated"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["industry"] == "Fintech"


@pytest.mark.asyncio
async def test_employee_count_parse_handles_invalid_input():
    service = _service_with(CompanyRepository())
    assert service._parse_employee_count("abc") is None
    assert service._parse_employee_count(None) is None
    assert service._parse_employee_count("12") == 12


@pytest.mark.asyncio
async def test_get_company_deals_requires_existing_company():
    repo: Any = CompanyRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_company_deals(db, "missing-company")
