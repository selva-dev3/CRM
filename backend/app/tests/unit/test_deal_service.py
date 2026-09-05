from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_deal(db, "missing-deal", organization_id="org-1")


@pytest.mark.asyncio
async def test_deal_timeline_reads_only_scoped_activities():
    deal = _make_deal()
    activity = type(
        "Activity",
        (),
        {
            "id": "activity-1",
            "action": "Deal won; quote QUO-1 created",
            "performed_by": "user-1",
            "timestamp": datetime(2026, 9, 5, tzinfo=UTC),
        },
    )()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    repo.list_activities = AsyncMock(return_value=[activity])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_deal_timeline(db, "deal-1", organization_id="org-1")

    assert result[0]["action"] == "Deal won; quote QUO-1 created"
    repo.list_activities.assert_awaited_once_with(db, deal_id="deal-1", organization_id="org-1")


@pytest.mark.asyncio
async def test_create_deal_defaults_to_authenticated_user(monkeypatch):
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
    result = await service.create_deal(db, payload, _user())

    assert result["id"] == "deal-1"
    created = repo.create.await_args_list[-1].kwargs["data"]
    assert created["assigned_to"] == "user-1"
    assert created["stage"] == "Qualification"


@pytest.mark.asyncio
async def test_create_deal_rejects_project_outside_current_organization(monkeypatch):
    repo: Any = DealRepository()
    repo.create = AsyncMock()
    project_repository = AsyncMock()
    project_repository.get.return_value = None
    service = DealService(repository=repo, project_repository=project_repository)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    with pytest.raises(NotFoundError):
        await service.create_deal(
            db,
            DealCreate(title="Project deal", project_id="project-2"),
            _user(),
        )

    project_repository.get.assert_awaited_once_with(
        db, project_id="project-2", organization_id="org-1"
    )
    repo.create.assert_not_awaited()


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
async def test_create_deal_stage_uses_current_organization(monkeypatch):
    repo: Any = DealRepository()
    repo.create_stage = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-2")
    )

    await service.create_deal_stage(
        db,
        name="Discovery",
        probability=25,
        current_user=_user(),
    )

    repo.create_stage.assert_awaited_once_with(
        db,
        organization_id="org-2",
        name="Discovery",
        probability=25,
    )


@pytest.mark.asyncio
async def test_list_deal_stages_is_scoped_to_current_organization(monkeypatch):
    repo: Any = DealRepository()
    repo.list_stages = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.deal_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-2")
    )

    assert await service.get_deal_stages(db, _user()) == []
    repo.list_stages.assert_awaited_once_with(db, organization_id="org-2")


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

    await service.create_deal(db, DealCreate(title="Acme Corp Deal", amount=25000.0), _user())

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["amount"] == 25000.0


@pytest.mark.asyncio
async def test_update_deal_nulls_company_on_sentinel():
    deal = _make_deal(company_id="comp-1")
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    payload = DealUpdate(company_id="null", title="Renamed")
    result = await service.update_deal(
        db, "deal-1", payload, organization_id="org-1", actor_id="user-1"
    )

    assert deal.company_id is None
    assert deal.title == "Renamed"
    assert result["company_id"] is None


@pytest.mark.asyncio
async def test_mark_deal_won_sets_stage_and_probability(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    service.quote_service = type(
        "Quotes",
        (),
        {
            "create_from_won_deal": AsyncMock(
                return_value=type(
                    "Quote",
                    (),
                    {
                        "id": "quote-1",
                        "quote_number": "QUO-1",
                        "total_amount": 24000,
                        "status": "Draft",
                    },
                )()
            )
        },
    )()
    result = await service.mark_deal_won(
        db, "deal-1", 30000.0, organization_id="org-1", actor_id="user-1"
    )

    assert deal.stage == "Closed Won"
    assert deal.probability == 100.0
    assert deal.amount == 24000.0  # Persisted product totals, not the browser amount.
    assert result["quote_id"] == "quote-1"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_mark_deal_won_does_not_commit_if_quote_creation_fails(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    service.quote_service = type(
        "Quotes",
        (),
        {
            "create_from_won_deal": AsyncMock(
                side_effect=APIException(message="Quote creation failed")
            )
        },
    )()
    with pytest.raises(APIException, match="Quote creation failed"):
        await service.mark_deal_won(
            db, "deal-1", 30000.0, organization_id="org-1", actor_id="user-1"
        )
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_deal_lost_fires_deal_lost_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.mark_deal_lost(db, "deal-1", "Budget cut", organization_id="org-1")

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.lost"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["reason"] == "Budget cut"


@pytest.mark.asyncio
async def test_add_deal_product_recalculates_amount():
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_product_scoped = AsyncMock(
        return_value=type(
            "Product",
            (),
            {
                "id": "prod-1",
                "name": "Service",
                "organization_id": "org-1",
                "is_active": True,
                "price": 500,
            },
        )()
    )
    repo.create_product = AsyncMock(return_value=type("P", (), {"id": "prod-1", "price": 500.0})())
    repo.get_deal_product = AsyncMock(return_value=None)
    repo.create_deal_product = AsyncMock(return_value=type("Line", (), {})())
    repo.list_deal_products = AsyncMock(
        return_value=[
            type(
                "DP",
                (),
                {"quantity": 2, "unit_price": 500.0, "discount_percent": 0, "tax_percent": 0},
            )()
        ]
    )
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    service.quote_service = type(
        "Quotes",
        (),
        {"repository": type("Repo", (), {"get_automatic": AsyncMock(return_value=None)})()},
    )()
    db = AsyncMock(spec=AsyncSession)

    result = await service.add_deal_product(
        db,
        deal_id="deal-1",
        product_id="prod-1",
        quantity=2,
        unit_price=500.0,
        custom_name=None,
        organization_id="org-1",
    )

    assert deal.amount == 1000.0
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_recalculate_deal_amount_uses_transaction_helper():
    deal = _make_deal(amount=25000.0)
    repo: Any = DealRepository()
    repo.list_deal_products = AsyncMock(
        return_value=[type("DP", (), {"quantity": 2, "unit_price": 500.0})()]
    )
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    service._commit = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service._recalculate_deal_amount(db, "deal-1", organization_id="org-1", force=True)

    assert deal.amount == 1000.0
    service._commit.assert_awaited_once_with(db, "Failed to recalculate deal amount")
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_deal_product_uses_deal_organization():
    deal = _make_deal(organization_id="org-2")
    product = type(
        "P",
        (),
        {
            "id": "prod-2",
            "price": 500.0,
            "name": "Implementation",
            "organization_id": "org-2",
            "is_active": True,
        },
    )()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    repo.get_product_scoped = AsyncMock(return_value=None)
    repo.get_product_by_sku = AsyncMock(return_value=None)
    repo.get_product_by_name = AsyncMock(return_value=None)
    repo.create_product = AsyncMock(return_value=product)
    repo.get_deal_product = AsyncMock(return_value=None)
    repo.create_deal_product = AsyncMock(return_value=type("Line", (), {})())
    repo.list_deal_products = AsyncMock(return_value=[])
    service = _service_with(repo)
    service.quote_service = type(
        "Quotes",
        (),
        {"repository": type("Repo", (), {"get_automatic": AsyncMock(return_value=None)})()},
    )()
    db = AsyncMock(spec=AsyncSession)

    await service.add_deal_product(
        db,
        deal_id="deal-1",
        product_id="",
        quantity=1,
        unit_price=500.0,
        custom_name="Implementation",
        organization_id="org-2",
    )

    repo.create_product.assert_awaited_once()
    assert repo.create_product.await_args.kwargs["organization_id"] == "org-2"
    assert repo.create_product.await_args.kwargs["name"] == "Implementation"
    assert repo.create_product.await_args.kwargs["sku"].startswith("CUSTOM-")


@pytest.mark.asyncio
async def test_clone_deal_returns_persisted_dates():
    original = _make_deal()
    clone = _make_deal(
        id="deal-2",
        title="Cloned deal",
        expected_close_date=date(2026, 9, 15),
        created_at=datetime(2026, 9, 4, 12, 30, tzinfo=UTC),
    )
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=original)
    repo.create = AsyncMock(return_value=clone)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.clone_deal(
        db,
        deal_id="deal-1",
        new_title="Cloned deal",
        organization_id="org-1",
    )

    assert result["expected_close_date"] == "2026-09-15"
    assert result["created_at"] == "2026-09-04T12:30:00+00:00"


@pytest.mark.asyncio
async def test_get_deal_commission_calculates_ten_percent():
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_deal(amount=50000.0))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_deal_commission(db, "deal-1", organization_id="org-1")

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
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    repo.user_exists = AsyncMock(return_value=True)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    result = await service.assign_deal(db, "deal-1", "user-2", organization_id="org-1")

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
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_deal_stage(
        db, "deal-1", "Proposal", organization_id="org-1", actor_id="user-1"
    )

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
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(
        db,
        "deal-1",
        DealUpdate(amount=40000.0),
        organization_id="org-1",
        actor_id="user-1",
    )

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
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(
        db,
        "deal-1",
        DealUpdate(amount=25000.0),
        organization_id="org-1",
        actor_id="user-1",
    )

    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_deal_fires_probability_changed_event(monkeypatch):
    deal = _make_deal()
    repo: Any = DealRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=deal)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_deal(
        db,
        "deal-1",
        DealUpdate(probability=80.0),
        organization_id="org-1",
        actor_id="user-1",
    )

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "deal.probability_changed"
    assert kwargs["data"]["old_probability"] == 20.0


@pytest.mark.asyncio
async def test_predict_win_rate_uses_shared_ai_service():
    repo: Any = DealRepository()
    ai_service = AsyncMock()
    ai_service.predict_deal_forecast.return_value = {
        "win_probability": 81.0,
        "key_drivers": ["Recent executive meeting"],
        "next_action": "Confirm procurement timeline",
        "risk_factors": ["No legal review date"],
        "run_id": "run-1",
    }
    service = DealService(repository=repo, ai_service_instance=ai_service)
    db = AsyncMock(spec=AsyncSession)
    actor = _user()

    result = await service.predict_deal_win_rate(db, "deal-1", actor)

    assert result == {
        "deal_id": "deal-1",
        "predicted_probability": 81.0,
        "key_drivers": ["Recent executive meeting"],
        "ai_recommendation": "Confirm procurement timeline",
        "risk_factors": ["No legal review date"],
        "run_id": "run-1",
    }
    ai_service.predict_deal_forecast.assert_awaited_once_with(db, "deal-1", actor)


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
