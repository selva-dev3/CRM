"""Conversion transaction and tenant-boundary regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Lead
from app.models.audit import AuditLog
from app.models.deal import DealActivity
from app.models.lead import LeadActivity
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import LeadConvertRequest
from app.services.lead_service import LeadService


def conversion_fixture():
    db = MagicMock(spec=AsyncSession)
    lead = Lead(
        id="lead",
        organization_id="org",
        title="Sale",
        company="Acme",
        contact_name="Buyer",
        email="buyer@example.test",
        status="Qualified",
        is_archived=False,
    )
    repository = MagicMock(spec=LeadRepository)
    repository.lock_conversion = AsyncMock(return_value=lead)
    repository.conversion_customers = AsyncMock(return_value=([], []))

    async def save(*args, **kwargs):
        await LeadRepository().save_conversion(*args, **kwargs)

    repository.save_conversion = AsyncMock(side_effect=save)
    user = SimpleNamespace(id="user", organization_id="org")
    return db, lead, repository, user


@pytest.mark.asyncio
@pytest.mark.parametrize("create_deal", [True, False])
async def test_conversion_persists_real_links_and_is_repeatable(create_deal):
    db, lead, repository, user = conversion_fixture()
    service = LeadService(repository=repository)
    result = await service.convert_lead(
        db, lead.id, LeadConvertRequest(create_deal=create_deal), user
    )
    assert result["company_id"] == lead.converted_company_id
    assert result["contact_id"] == lead.converted_contact_id
    assert bool(result["deal_id"]) == create_deal
    assert lead.status == "Converted"
    assert lead.converted_at is not None
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(
        isinstance(record, AuditLog) and record.action == "lead.converted" for record in added
    )
    assert any(isinstance(record, LeadActivity) for record in added)
    assert any(isinstance(record, DealActivity) for record in added) is create_deal
    assert await service.convert_lead(db, lead.id, LeadConvertRequest(), user) == result
    lead.status = "Qualified"
    assert await service.convert_lead(db, lead.id, LeadConvertRequest(), user) == result
    repository.conversion_customers.assert_awaited_once()
    repository.lock_conversion.assert_awaited_with(db, "lead", "org")
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("lead_status", ["New", "Unqualified", "Contacted", "Converted"])
async def test_invalid_or_legacy_conversion_is_rejected(lead_status):
    db, lead, repository, user = conversion_fixture()
    lead.status = lead_status
    with pytest.raises(APIException):
        await LeadService(repository=repository).convert_lead(
            db, lead.id, LeadConvertRequest(), user
        )
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_missing_or_foreign_lead_is_not_found():
    db, lead, repository, user = conversion_fixture()
    repository.lock_conversion.return_value = None
    with pytest.raises(NotFoundError):
        await LeadService(repository=repository).convert_lead(
            db, lead.id, LeadConvertRequest(), user
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_database_failure_rolls_back_conversion():
    db, lead, repository, user = conversion_fixture()
    db.flush.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await LeadService(repository=repository).convert_lead(
            db, lead.id, LeadConvertRequest(), user
        )
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_customer_is_rejected():
    db, lead, repository, user = conversion_fixture()
    repository.conversion_customers.return_value = ([object(), object()], [])
    with pytest.raises(APIException, match="duplicate customers"):
        await LeadService(repository=repository).convert_lead(
            db, lead.id, LeadConvertRequest(), user
        )
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_conversion_amount_is_finite_and_nonnegative(amount):
    with pytest.raises(ValidationError):
        LeadConvertRequest(deal_amount=amount)
