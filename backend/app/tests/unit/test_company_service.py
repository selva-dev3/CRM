from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.company import Company
from app.models.deal import Deal
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
async def test_list_companies_is_scoped_to_current_organization(monkeypatch):
    repo: Any = CompanyRepository()
    repo.list_by_org = AsyncMock(return_value=[_make_company()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.company_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.list_companies(
        db, page=2, limit=15, search="Acme", current_user=AsyncMock()
    )

    assert result[0]["id"] == "cmp-1"
    repo.list_by_org.assert_awaited_once_with(
        db,
        organization_id="org-1",
        page=2,
        limit=15,
        search="Acme",
    )


@pytest.mark.asyncio
async def test_count_companies_is_scoped_to_current_organization(monkeypatch):
    repo: Any = CompanyRepository()
    repo.count_by_org = AsyncMock(return_value=23)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.company_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.count_companies(db, search="Acme", current_user=AsyncMock())

    assert result == 23
    repo.count_by_org.assert_awaited_once_with(db, organization_id="org-1", search="Acme")


@pytest.mark.asyncio
async def test_get_company_raises_not_found_when_missing():
    repo: Any = CompanyRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_company(db, "missing-company", organization_id="org-1")


@pytest.mark.asyncio
async def test_get_company_deals_is_scoped_and_serialized():
    company = _make_company()
    repo: Any = CompanyRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=company)
    service = _service_with(repo)
    service.deal_repository.list_by_company = AsyncMock(
        return_value=[Deal(id="deal-1", organization_id="org-1", title="Expansion")]
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_company_deals(db, "cmp-1", organization_id="org-1")

    assert result[0]["id"] == "deal-1"
    service.deal_repository.list_by_company.assert_awaited_once_with(
        db, company_id="cmp-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_set_parent_company_rejects_self_reference():
    company = _make_company()
    repo: Any = CompanyRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=company)
    repo.set_parent = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.core.errors import APIException

    with pytest.raises(APIException):
        await service.set_parent_company(
            db, "cmp-1", "cmp-1", organization_id="org-1"
        )

    repo.set_parent.assert_not_called()


@pytest.mark.asyncio
async def test_set_parent_company_rejects_hierarchy_cycle():
    company = _make_company(id="cmp-1")
    parent = _make_company(id="cmp-2", parent_company_id="cmp-1")
    repo: Any = CompanyRepository()
    repo.get_by_id_scoped = AsyncMock(side_effect=[company, parent, company])
    repo.set_parent = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.core.errors import APIException

    with pytest.raises(APIException):
        await service.set_parent_company(
            db, "cmp-1", "cmp-2", organization_id="org-1"
        )

    repo.set_parent.assert_not_called()


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
async def test_create_company_validates_and_persists_custom_fields(monkeypatch):
    company = _make_company(custom_fields={"account_tier": "Gold"})
    repo: Any = CompanyRepository()
    repo.create = AsyncMock(return_value=company)
    custom_fields = AsyncMock()
    custom_fields.validate_values.return_value = {"account_tier": "Gold"}
    service = CompanyService(repository=repo, custom_field_service_instance=custom_fields)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.company_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_company(
        db,
        CompanyCreate(name="Acme Inc", custom_fields={"account_tier": "Gold"}),
    )

    custom_fields.validate_values.assert_awaited_once_with(
        db,
        organization_id="org-1",
        entity_type="Company",
        values={"account_tier": "Gold"},
    )
    assert repo.create.await_args.kwargs["data"]["custom_fields"] == {"account_tier": "Gold"}
    assert result["custom_fields"] == {"account_tier": "Gold"}


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
    repo.get_by_id_scoped = AsyncMock(return_value=company)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_company(
        db,
        "cmp-1",
        CompanyUpdate(industry="Fintech"),
        organization_id="org-1",
    )

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
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_company_deals(db, "missing-company", organization_id="org-1")
