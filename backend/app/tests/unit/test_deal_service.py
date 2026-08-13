from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.schemas.crm_schemas import DealCreate, DealUpdate
from app.services.deal_service import DealService, deal_to_dict


def _make_deal(**overrides) -> Deal:
    defaults = {
        "id": "deal-1",
        "organization_id": "org-1",
        "title": "Acme Corp Deal",
        "amount": 25000.0,
        "stage": "Qualification",
        "probability": 20.0,
        "assigned_to": "user-1",
        "company_id": None,
        "contact_id": None,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Deal(**defaults)


def _service_with(repo: DealRepository) -> DealService:
    return DealService(repository=repo)


@pytest.mark.asyncio
async def test_list_deals_serializes_rows():
    repo = DealRepository()
    repo.list = AsyncMock(return_value=[_make_deal()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_deals(db, page=1, limit=20)

    assert len(result) == 1
    assert result[0]["id"] == "deal-1"
    assert result[0]["title"] == "Acme Corp Deal"
    repo.list.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_deal_raises_not_found_when_missing():
    repo = DealRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_deal(db, "missing-deal")


@pytest.mark.asyncio
async def test_create_deal_falls_back_to_first_user(monkeypatch):
    deal = _make_deal()
    repo = DealRepository()
    repo.create = AsyncMock(return_value=deal)
    repo.user_exists = AsyncMock(return_value=False)
    repo.first_user_id = AsyncMock(return_value="user-1")
    repo.company_exists = AsyncMock(return_value=True)
    repo.contact_exists = AsyncMock(return_value=False)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = DealCreate(title="Acme Corp Deal", amount=25000.0)
    result = await service.create_deal(db, payload, None)

    assert result["id"] == "deal-1"
    created = repo.create.await_args.kwargs["data"]
    assert created["assigned_to"] == "user-1"
    assert created["stage"] == "Qualification"


@pytest.mark.asyncio
async def test_update_deal_nulls_company_on_sentinel():
    deal = _make_deal(company_id="comp-1")
    repo = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    payload = DealUpdate(company_id="null", title="Renamed")
    result = await service.update_deal(db, "deal-1", payload)

    assert deal.company_id is None
    assert deal.title == "Renamed"
    assert result["company_id"] is None


@pytest.mark.asyncio
async def test_mark_deal_won_sets_stage_and_probability():
    deal = _make_deal()
    repo = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.mark_deal_won(db, "deal-1", 30000.0)

    assert deal.stage == "Closed Won"
    assert deal.probability == 100.0
    assert deal.amount == 30000.0
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_add_deal_product_recalculates_amount():
    deal = _make_deal()
    repo = DealRepository()
    repo.get_product = AsyncMock(return_value=None)
    repo.create_product = AsyncMock(
        return_value=type("P", (), {"id": "prod-1", "price": 500.0})()
    )
    repo.get_deal_product = AsyncMock(return_value=None)
    repo.create_deal_product = AsyncMock()
    repo.list_deal_products = AsyncMock(
        return_value=[type("DP", (), {"quantity": 2, "unit_price": 500.0})()]
    )
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.add_deal_product(
        db,
        deal_id="deal-1",
        product_id="prod-1",
        quantity=2,
        unit_price=500.0,
        custom_name=None,
    )

    assert deal.amount == 1000.0
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_deal_commission_calculates_ten_percent():
    repo = DealRepository()
    repo.get_by_id = AsyncMock(return_value=_make_deal(amount=50000.0))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_deal_commission(db, "deal-1")

    assert result["estimated_commission"] == 5000.0
    assert result["commission_rate_pct"] == 10.0


def test_deal_to_dict_handles_missing_dates():
    d = _make_deal(created_at=None, expected_close_date=None)
    assert deal_to_dict(d)["created_at"] is None
    assert deal_to_dict(d)["expected_close_date"] is None


@pytest.mark.asyncio
async def test_predict_win_rate_fallback_for_closed_won():
    repo = DealRepository()
    repo.get_by_id = AsyncMock(
        return_value=_make_deal(stage="Closed Won", probability=50.0)
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import note_service

    note_service.get_notes_by_entity = AsyncMock(return_value=[])

    result = await service.predict_deal_win_rate(db, "deal-1")

    assert result["predicted_probability"] == 100.0
    assert result["model"] == "crm-sales-analytics-engine"