from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import User
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.dashboard import CustomWidgetSaveRequest, DashboardAiInsightsResponse
from app.services.dashboard_service import DashboardService


def _service_with(repo: DashboardRepository, setting_repo: SettingRepository) -> DashboardService:
    return DashboardService(repository=repo, setting_repository=setting_repo)


@pytest.mark.asyncio
async def test_get_kpis_computes_win_rate():
    repo = DashboardRepository()
    repo.count_leads = AsyncMock(return_value=10)
    repo.sum_pipeline_deals = AsyncMock(return_value=12000.0)
    repo.sum_won_deals = AsyncMock(return_value=5000.0)
    repo.count_closed_deals = AsyncMock(return_value=8)
    repo.count_won_deals = AsyncMock(return_value=2)
    repo.avg_lead_score = AsyncMock(return_value=0.0)
    repo.count_scored_leads = AsyncMock(return_value=10)
    repo.get_organization_currency_locale = AsyncMock(return_value=("INR", "en-IN"))
    repo.recent_leads = AsyncMock(return_value=[])
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_kpis(db, "org-1")

    assert result.total_leads == 10
    assert result.deals_won_amount == 5000.0
    assert result.pipeline_revenue == 12000.0
    assert result.win_rate_percentage == 25.0
    assert result.won_deals_count == 2
    assert result.closed_deals_count == 8
    assert result.ai_lead_score_avg == 0.0
    assert result.scored_leads_count == 10
    assert result.currency == "INR"
    assert result.locale == "en-IN"
    repo.count_leads.assert_awaited_once_with(db, "org-1")


@pytest.mark.asyncio
async def test_get_kpis_uses_lead_contact_name_for_recent_activity():
    repo = DashboardRepository()
    repo.count_leads = AsyncMock(return_value=1)
    repo.sum_pipeline_deals = AsyncMock(return_value=0.0)
    repo.sum_won_deals = AsyncMock(return_value=0.0)
    repo.count_closed_deals = AsyncMock(return_value=0)
    repo.count_won_deals = AsyncMock(return_value=0)
    repo.avg_lead_score = AsyncMock(return_value=0.0)
    repo.count_scored_leads = AsyncMock(return_value=0)
    repo.get_organization_currency_locale = AsyncMock(return_value=("USD", "en-US"))
    repo.recent_leads = AsyncMock(
        return_value=[
            SimpleNamespace(
                contact_name="Ada Lovelace",
                title="CTO",
                email="ada@example.com",
                created_at=datetime(2026, 8, 31, 12, 30, tzinfo=UTC),
            )
        ]
    )
    service = _service_with(repo, SettingRepository())

    result = await service.get_kpis(AsyncMock(spec=AsyncSession), "org-1")

    assert result.recent_activity[0].title == "Ada Lovelace"


@pytest.mark.asyncio
async def test_get_sales_funnel_orders_standard_stages_first():
    repo = DashboardRepository()
    repo.deal_stage_totals = AsyncMock(
        return_value=[("Closed Won", 3, 1000.0), ("Custom Stage", 1, 50.0)]
    )
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_sales_funnel(db, "org-1")

    stages = [item["stage"] for item in result]
    assert stages.index("Prospecting") == 0
    assert stages.index("Closed Won") == 4
    assert stages[-1] == "Custom Stage"


@pytest.mark.asyncio
async def test_get_custom_widgets_returns_defaults_when_unset():
    setting_repo = SettingRepository()
    setting_repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_custom_widgets(db, "org-1")

    assert len(result) == 5
    assert result[0]["id"] == "w-kpis"
    assert all(widget["id"] != "w-revenue" for widget in result)
    setting_repo.get_by_key.assert_awaited_once_with(db, "dashboard_custom_widgets:org-1")


@pytest.mark.asyncio
async def test_get_custom_widgets_returns_defaults_for_corrupt_json():
    setting_repo = SettingRepository()
    setting_repo.get_by_key = AsyncMock(return_value=SimpleNamespace(value="{not-json"))
    service = _service_with(DashboardRepository(), setting_repo)

    result = await service.get_custom_widgets(AsyncMock(spec=AsyncSession), "org-1")

    assert result == DashboardService.DEFAULT_WIDGETS


@pytest.mark.asyncio
async def test_save_custom_widgets_persists_preferences():
    setting_repo = SettingRepository()
    setting_repo.upsert = AsyncMock()
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.save_custom_widgets(db, "org-1", [{"id": "w-kpis", "enabled": True}])

    assert result["status"] == "success"
    setting_repo.upsert.assert_awaited_once_with(
        db,
        key="dashboard_custom_widgets:org-1",
        value='[{"id": "w-kpis", "enabled": true}]',
    )


@pytest.mark.asyncio
async def test_save_custom_widgets_returns_generic_error_for_serialization_failure(monkeypatch):
    setting_repo = SettingRepository()
    setting_repo.upsert = AsyncMock()
    service = _service_with(DashboardRepository(), setting_repo)

    def fail_serialization(_widgets):
        raise TypeError("internal serialization details")

    monkeypatch.setattr("app.services.dashboard_service.json.dumps", fail_serialization)

    with pytest.raises(APIException) as exc_info:
        await service.save_custom_widgets(AsyncMock(spec=AsyncSession), "org-1", [])

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_WIDGET_PREFERENCES"
    assert exc_info.value.message == "Dashboard widget preferences contain unsupported values."
    assert "internal serialization details" not in exc_info.value.message
    setting_repo.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_custom_widgets_rolls_back_upsert_failure():
    setting_repo = SettingRepository()
    setting_repo.upsert = AsyncMock(side_effect=RuntimeError("database unavailable"))
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.save_custom_widgets(db, "org-1", [])

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_custom_widgets_rolls_back_commit_failure():
    setting_repo = SettingRepository()
    setting_repo.upsert = AsyncMock()
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.save_custom_widgets(db, "org-1", [])

    setting_repo.upsert.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_activities_summary_counts_each_metric():
    repo = DashboardRepository()
    repo.get_organization_timezone = AsyncMock(return_value="UTC")
    repo.count_calls = AsyncMock(return_value=5)
    repo.count_emails = AsyncMock(return_value=8)
    repo.count_meetings = AsyncMock(return_value=2)
    repo.count_completed_tasks = AsyncMock(return_value=11)
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_activities_summary(db, "org-1")

    assert result["calls_completed"] == 5
    assert result["emails_sent"] == 8
    assert result["meetings_held"] == 2
    assert result["tasks_completed"] == 11
    assert result["period_label"] == "Today · UTC"
    assert repo.count_calls.await_args.args[1] == "org-1"


@pytest.mark.asyncio
async def test_get_lead_conversions_merges_equivalent_urls():
    repo = DashboardRepository()
    repo.lead_source_conversions = AsyncMock(
        return_value=[("https://Selv.in/", 2, 1), ("https://selv.in", 3, 2)]
    )
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_lead_conversions(db, "org-1")

    assert result == [{"source": "selv.in", "leads": 5, "converted": 3, "rate": 60.0}]
    repo.lead_source_conversions.assert_awaited_once_with(db, "org-1")


@pytest.mark.asyncio
async def test_get_recent_deals_uses_owner_name_and_updated_timestamp():
    repo = DashboardRepository()
    updated_at = datetime(2026, 8, 31, 12, 30, tzinfo=UTC)
    deal = SimpleNamespace(
        id="deal-1",
        title="Enterprise renewal",
        amount=5000,
        stage="Negotiation",
        updated_at=updated_at,
    )
    repo.recent_deals = AsyncMock(return_value=[(deal, "Grace Hopper")])
    service = _service_with(repo, SettingRepository())

    result = await service.get_recent_deals(AsyncMock(spec=AsyncSession), "org-1")

    assert result[0]["owner"] == "Grace Hopper"
    assert result[0]["updated_at"] == "2026-08-31"


@pytest.mark.asyncio
async def test_recent_deals_owner_join_excludes_inactive_users():
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.all.return_value = []
    db.execute.return_value = result

    await DashboardRepository().recent_deals(db, "org-1")

    statement = db.execute.await_args.args[0]
    owner_join = statement.get_final_froms()[0]
    assert any(
        condition.compare(User.is_active.is_(True)) for condition in owner_join.onclause.clauses
    )


@pytest.mark.asyncio
async def test_organization_currency_locale_is_normalized():
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.first.return_value = (" usd ", "en-US")
    db.execute.return_value = result

    currency, locale = await DashboardRepository().get_organization_currency_locale(db, "org-1")

    assert currency == "USD"
    assert locale == "en-US"


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_currency", ["$", "US Dollar", "   ", "USDX", None])
async def test_organization_currency_locale_falls_back_for_invalid_currency(stored_currency):
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.first.return_value = (stored_currency, "en-IN")
    db.execute.return_value = result

    currency, locale = await DashboardRepository().get_organization_currency_locale(db, "org-1")

    assert currency == "INR"
    assert locale == "en-IN"


@pytest.mark.asyncio
async def test_ai_insight_includes_deal_identifier():
    repo = DashboardRepository()
    repo.count_leads = AsyncMock(return_value=1)
    repo.count_deals_and_sum = AsyncMock(return_value=(1, 5000.0))
    repo.get_organization_currency_locale = AsyncMock(return_value=("INR", "en-IN"))
    repo.top_deal = AsyncMock(
        return_value=SimpleNamespace(
            id="deal-1",
            title="Enterprise renewal",
            amount=5000.0,
            stage="Negotiation",
        )
    )
    service = _service_with(repo, SettingRepository())

    result = await service.get_ai_insights(AsyncMock(spec=AsyncSession), "org-1")

    assert result["insights"][0]["deal_id"] == "deal-1"
    assert "INR 5,000.00" in result["summary"]
    assert "INR 5,000.00" in result["insights"][0]["description"]
    assert DashboardAiInsightsResponse.model_validate(result).insights[0].deal_id == "deal-1"


@pytest.mark.asyncio
async def test_revenue_chart_reports_missing_source_data():
    service = _service_with(DashboardRepository(), SettingRepository())

    with pytest.raises(APIException) as exc_info:
        await service.get_revenue_chart(AsyncMock(spec=AsyncSession), "org-1")

    assert exc_info.value.status_code == 501
    assert exc_info.value.code == "METRIC_UNAVAILABLE"


def test_custom_widget_request_rejects_malformed_payload():
    with pytest.raises(ValidationError):
        CustomWidgetSaveRequest.model_validate(
            {"id": "not-a-widget-id", "title": "KPIs", "enabled": "yes", "extra": True}
        )
