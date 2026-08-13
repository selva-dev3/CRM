from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Lead
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import LeadCreate
from app.services.lead_service import LeadService


def _make_lead(**overrides) -> Lead:
    defaults = {
        "id": "lead-1",
        "organization_id": "org-1",
        "title": "Acme Corp",
        "company": "Acme Inc",
        "contact_name": "Jane Doe",
        "email": "jane@acme.com",
        "phone": None,
        "website": None,
        "industry": None,
        "company_size": None,
        "country": None,
        "state": None,
        "city": None,
        "address": None,
        "postal_code": None,
        "status": "New",
        "source": "Website",
        "score": 50.0,
        "assigned_to": None,
        "is_archived": False,
    }
    defaults.update(overrides)
    return Lead(**defaults)


def _service_with(repo: LeadRepository) -> LeadService:
    return LeadService(repository=repo)


@pytest.mark.asyncio
async def test_list_leads_returns_serialized_dicts():
    repo = LeadRepository()
    repo.list_leads = AsyncMock(return_value=[_make_lead()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_leads(db, page=1, limit=20)

    assert len(result) == 1
    assert result[0]["id"] == "lead-1"
    assert result[0]["contact_name"] == "Jane Doe"
    assert result[0]["organization_id"] == "org-1"
    assert result[0]["created_at"] == "2026-01-01"


@pytest.mark.asyncio
async def test_get_lead_raises_not_found_when_missing():
    repo = LeadRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_lead(db, "missing-lead")


@pytest.mark.asyncio
async def test_create_lead_resolves_org_and_serializes():
    lead = _make_lead()
    repo = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=object())
    repo.get_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(title="Acme Corp", company="Acme Inc", contact_name="Jane Doe", email="jane@acme.com")
    result = await service.create_lead(db, payload)

    assert result["id"] == "lead-1"
    assert result["status"] == "New"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_lead_only_applies_provided_fields():
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id = AsyncMock(return_value=lead)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    result = await service.update_lead(db, "lead-1", LeadUpdate(status="Qualified"))

    assert result["status"] == "Qualified"
    assert lead.status == "Qualified"
    assert lead.title == "Acme Corp"