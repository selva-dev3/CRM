from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.schemas.crm_schemas import DealCreate, DealCustomFieldDefinition, DealUpdate
from app.services.deal_service import DealService, deal_to_dict
from app.services.integration_service import integration_service
from app.services.quote_service import QuoteService


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
        "custom_fields": {},
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Deal(**defaults)


def _service_with(repo: DealRepository) -> DealService:
    return DealService(repository=repo)


def _user() -> User:
    return User(id="user-1", email="user@crm.com", organization_id="org-1")


@pytest.mark.asyncio
async def test_list_deals_serializes_rows():
    repo: Any = DealRepository()
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
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_deal(db, "missing-deal")


@pytest.mark.asyncio
async def test_create_deal_falls_back_to_first_user(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
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
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())

    payload = DealCreate(title="Acme Corp Deal", amount=25000.0)
    result = await service.create_deal(db, payload, None)

    assert result["id"] == "deal-1"
    created = repo.create.await_args_list[-1].kwargs["data"]
    assert created["assigned_to"] == "user-1"
    assert created["stage"] == "Qualification"


@pytest.mark.asyncio
async def test_create_deal_validates_and_persists_custom_fields(monkeypatch):
    deal = _make_deal(custom_fields={"decision_maker": "CTO"})
    repo: Any = DealRepository()
    repo.create = AsyncMock(return_value=deal)
    repo.user_exists = AsyncMock(return_value=True)
    repo.company_exists = AsyncMock(return_value=True)
    repo.contact_exists = AsyncMock(return_value=True)
    field_repo = AsyncMock()
    field_repo.list_custom_fields.return_value = [
        type(
            "Field",
            (),
            {
                "field_name": "decision_maker",
                "field_type": "text",
                "options": [],
            },
        )()
    ]
    service = DealService(repository=repo, setting_repository=field_repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_deal(
        db,
        DealCreate(
            title="Acme Corp Deal",
            assigned_to="user-1",
            custom_fields={"decision_maker": "CTO"},
        ),
        _user(),
    )

    assert repo.create.await_args.kwargs["data"]["custom_fields"] == {"decision_maker": "CTO"}
    assert result["custom_fields"] == {"decision_maker": "CTO"}


@pytest.mark.asyncio
async def test_list_custom_fields_returns_typed_definitions(monkeypatch):
    repo: Any = DealRepository()
    field_repo = AsyncMock()
    field_repo.list_custom_fields.return_value = [
        type(
            "Field",
            (),
            {
                "field_name": "sales_region",
                "field_type": "select",
                "label": "Sales Region",
                "options": ["North", "South"],
            },
        )()
    ]
    service = DealService(repository=repo, setting_repository=field_repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.list_custom_fields(db, _user())

    assert result == [
        DealCustomFieldDefinition(
            field_name="sales_region",
            field_type="select",
            label="Sales Region",
            options=["North", "South"],
        )
    ]
    field_repo.list_custom_fields.assert_awaited_once_with(
        db, organization_id="org-1", entity_type="Deal"
    )


@pytest.mark.asyncio
async def test_create_deal_rejects_unknown_custom_field(monkeypatch):
    repo: Any = DealRepository()
    repo.create = AsyncMock()
    field_repo = AsyncMock()
    field_repo.list_custom_fields.return_value = []
    service = DealService(repository=repo, setting_repository=field_repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_deal(
            db,
            DealCreate(title="Acme Corp Deal", custom_fields={"foreign_field": "value"}),
            _user(),
        )

    assert getattr(exc_info.value, "code", None) == "INVALID_CUSTOM_FIELDS"
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_deal_fires_deal_created_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.create = AsyncMock(return_value=deal)
    repo.user_exists = AsyncMock(return_value=False)
    repo.first_user_id = AsyncMock(return_value="user-1")
    repo.company_exists = AsyncMock(return_value=True)
    repo.contact_exists = AsyncMock(return_value=False)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.create_deal(db, DealCreate(title="Acme Corp Deal", amount=25000.0), None)

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["amount"] == 25000.0


@pytest.mark.asyncio
async def test_update_deal_nulls_company_on_sentinel():
    deal = _make_deal(company_id="comp-1")
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    payload = DealUpdate(company_id="null", title="Renamed")
    result = await service.update_deal(db, "deal-1", payload)

    assert deal.company_id is None
    assert deal.title == "Renamed"
    assert result["company_id"] is None


@pytest.mark.asyncio
async def test_mark_deal_won_sets_stage_and_probability(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    result = await service.mark_deal_won(db, "deal-1", 30000.0)

    assert deal.stage == "Closed Won"
    assert deal.probability == 100.0
    assert deal.amount == 30000.0
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_mark_deal_won_fires_deal_won_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_deal_won(db, "deal-1", 30000.0)

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.won"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["amount"] == 30000.0
    assert kwargs["data"]["stage"] == "Closed Won"


@pytest.mark.asyncio
async def test_mark_deal_lost_fires_deal_lost_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_deal_lost(db, "deal-1", "Budget cut")

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.lost"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["reason"] == "Budget cut"


@pytest.mark.asyncio
async def test_add_deal_product_recalculates_amount():
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_product = AsyncMock(return_value=None)
    repo.create_product = AsyncMock(return_value=type("P", (), {"id": "prod-1", "price": 500.0})())
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
    repo: Any = DealRepository()
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
async def test_assign_deal_fires_deal_assigned_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    result = await service.assign_deal(db, "deal-1", "user-2")

    assert result["status"] == "success"
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.assigned"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["assigned_to"] == "user-2"


@pytest.mark.asyncio
async def test_update_deal_stage_fires_deal_stage_changed_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_deal_stage(db, "deal-1", "Proposal")

    assert result["status"] == "success"
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.stage_changed"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["stage"] == "Proposal"


@pytest.mark.asyncio
async def test_update_deal_fires_amount_changed_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(db, "deal-1", DealUpdate(amount=40000.0))

    assert deal.amount == 40000.0
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.amount_changed"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["old_amount"] == 25000.0


@pytest.mark.asyncio
async def test_update_deal_no_amount_event_when_unchanged(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(db, "deal-1", DealUpdate(amount=25000.0))

    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_deal_fires_probability_changed_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(db, "deal-1", DealUpdate(probability=80.0))

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.probability_changed"
    assert kwargs["data"]["old_probability"] == 20.0


@pytest.mark.asyncio
async def test_predict_win_rate_fallback_for_closed_won(monkeypatch):
    repo: Any = DealRepository()
    repo.get_by_id = AsyncMock(return_value=_make_deal(stage="Closed Won", probability=50.0))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import note_service

    async def empty_notes(*_args, **_kwargs):
        return []

    monkeypatch.setattr(note_service, "get_notes_by_entity", empty_notes)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = await service.predict_deal_win_rate(db, "deal-1", _user())

    assert result["predicted_probability"] == 100.0
    assert result["model"] == "crm-sales-analytics-engine"


@pytest.mark.asyncio
async def test_get_deal_quotes_uses_scoped_deal_and_quote_service():
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_deal())
    quotes = AsyncMock(spec=QuoteService)
    quotes.list_quotes_for_deal.return_value = [{"id": "quote-1"}]
    service = DealService(repository=repo, quote_service_instance=quotes)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_deal_quotes(db, "deal-1", "org-1")

    assert result == [{"id": "quote-1"}]
    repo.get_by_id_scoped.assert_awaited_once_with(db, deal_id="deal-1", organization_id="org-1")
    quotes.list_quotes_for_deal.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("deal_id", ["foreign-deal", "missing-deal"])
async def test_get_deal_quotes_hides_foreign_and_missing_deals(deal_id):
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    quotes = AsyncMock(spec=QuoteService)
    service = DealService(repository=repo, quote_service_instance=quotes)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_deal_quotes(db, deal_id, "org-1")

    repo.get_by_id_scoped.assert_awaited_once_with(db, deal_id=deal_id, organization_id="org-1")
    quotes.list_quotes_for_deal.assert_not_awaited()
