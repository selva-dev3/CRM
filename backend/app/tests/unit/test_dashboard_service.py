from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import dashboard as dashboard_router
from app.api.v1.routers.dashboard import _validate_date_range
from app.core.errors import APIException
from app.models import Lead, User
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.dashboard import CustomWidgetSaveRequest, DashboardAiInsightsResponse
from app.services.dashboard_service import DashboardService
from app.services.record_access_service import record_access_service

FINANCIAL_KPIS = {
    "quote_count": 3,
    "quote_value": 9000.0,
    "quote_conversion_percentage": 50.0,
    "invoice_count": 2,
    "invoice_total": 6000.0,
    "paid_amount": 4000.0,
    "outstanding_amount": 2000.0,
    "pending_payment_count": 1,
    "partially_paid_invoice_count": 0,
    "paid_invoice_count": 1,
    "revenue": 4000.0,
    "collection_rate_percentage": 66.67,
}


class _AggregateResult:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


@pytest.mark.asyncio
async def test_financial_kpis_query_is_tenant_currency_and_date_scoped():
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _AggregateResult((0, 0, 0, 0)),
        _AggregateResult((0, 0, 0, 0, 0, 0, 0)),
        _ScalarResult(1250),
    ]
    start_at = datetime(2026, 1, 1, tzinfo=UTC)
    end_at = datetime(2026, 2, 1, tzinfo=UTC)

    result = await DashboardRepository().financial_kpis(
        db,
        "org-1",
        currency="INR",
        start_at=start_at,
        end_at=end_at,
    )

    quote_statement = db.execute.await_args_list[0].args[0]
    invoice_statement = db.execute.await_args_list[1].args[0]
    payment_statement = db.execute.await_args_list[2].args[0]
    quote_sql = str(quote_statement)
    invoice_sql = str(invoice_statement)
    payment_sql = str(payment_statement)
    assert "upper(quotes.currency)" in quote_sql
    assert "quotes.created_at >=" in quote_sql and "quotes.created_at <" in quote_sql
    assert "upper(invoices.currency)" in invoice_sql
    assert "invoices.created_at >=" in invoice_sql and "invoices.created_at <" in invoice_sql
    assert "org-1" in quote_statement.compile().params.values()
    assert "INR" in quote_statement.compile().params.values()
    assert "org-1" in invoice_statement.compile().params.values()
    assert "INR" in invoice_statement.compile().params.values()
    assert "payments.paid_at >=" in payment_sql and "payments.paid_at <" in payment_sql
    assert "upper(payments.currency)" in payment_sql
    assert result["revenue"] == 1250.0


@pytest.mark.asyncio
async def test_kpi_domain_metrics_use_one_aggregate_query_each():
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        _AggregateResult((12, 74.25, 8)),
        _AggregateResult((25000.0, 9000.0, 4, 3)),
    ]
    repository = DashboardRepository()
    start_at = datetime(2026, 1, 1, tzinfo=UTC)
    end_at = datetime(2026, 2, 1, tzinfo=UTC)

    lead_metrics = await repository.lead_kpi_metrics(db, "org-1", start_at=start_at, end_at=end_at)
    deal_metrics = await repository.deal_kpi_metrics(db, "org-1", start_at=start_at, end_at=end_at)

    assert db.execute.await_count == 2
    assert lead_metrics == {"total_leads": 12, "average_score": 74.2, "scored_leads": 8}
    assert deal_metrics == {
        "pipeline_revenue": 25000.0,
        "deals_won_amount": 9000.0,
        "closed_deals": 4,
        "won_deals": 3,
    }


def _service_with(
    repo: DashboardRepository,
    setting_repo: SettingRepository,
    ai_service: Any | None = None,
) -> DashboardService:
    return DashboardService(
        repository=repo,
        setting_repository=setting_repo,
        ai_service_instance=ai_service,
    )


@pytest.mark.asyncio
async def test_get_kpis_computes_win_rate():
    repo: Any = DashboardRepository()
    repo.lead_kpi_metrics = AsyncMock(
        return_value={"total_leads": 10, "average_score": 0.0, "scored_leads": 10}
    )
    repo.deal_kpi_metrics = AsyncMock(
        return_value={
            "pipeline_revenue": 12000.0,
            "deals_won_amount": 5000.0,
            "closed_deals": 8,
            "won_deals": 2,
        }
    )
    repo.financial_kpis = AsyncMock(return_value=FINANCIAL_KPIS)
    repo.get_organization_currency_locale = AsyncMock(return_value=("INR", "en-IN"))
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
    assert result.outstanding_amount == 2000.0
    assert result.currency == "INR"
    assert result.locale == "en-IN"
    repo.lead_kpi_metrics.assert_awaited_once_with(db, "org-1", None, start_at=None, end_at=None)
    repo.financial_kpis.assert_awaited_once_with(
        db,
        "org-1",
        currency="INR",
        start_at=None,
        end_at=None,
        quote_access=None,
        invoice_access=None,
        payment_access=None,
    )


@pytest.mark.asyncio
async def test_get_kpis_scopes_financial_values_to_currency_and_date_range():
    repo: Any = DashboardRepository()
    repo.lead_kpi_metrics = AsyncMock(
        return_value={"total_leads": 0, "average_score": 0.0, "scored_leads": 0}
    )
    repo.deal_kpi_metrics = AsyncMock(
        return_value={
            "pipeline_revenue": 0.0,
            "deals_won_amount": 0.0,
            "closed_deals": 0,
            "won_deals": 0,
        }
    )
    repo.financial_kpis = AsyncMock(return_value=FINANCIAL_KPIS)
    repo.get_organization_currency_locale = AsyncMock(return_value=("EUR", "de-DE"))
    service = _service_with(repo, SettingRepository())
    start_at = datetime(2026, 1, 1, tzinfo=UTC)
    end_at = datetime(2026, 2, 1, tzinfo=UTC)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_kpis(
        db,
        "org-1",
        start_at=start_at,
        end_at=end_at,
    )

    assert repo.financial_kpis.await_count == 2
    repo.financial_kpis.assert_any_await(
        db,
        "org-1",
        currency="EUR",
        start_at=start_at,
        end_at=end_at,
        quote_access=None,
        invoice_access=None,
        payment_access=None,
    )
    assert result.period is not None
    assert result.period.start_at == start_at
    assert result.comparisons is not None
    assert result.comparisons.total_leads.change_percentage is None
    assert result.comparisons.revenue.change_percentage == 0.0


@pytest.mark.asyncio
async def test_get_kpis_does_not_fetch_unused_recent_activity():
    repo: Any = DashboardRepository()
    repo.lead_kpi_metrics = AsyncMock(
        return_value={"total_leads": 1, "average_score": 0.0, "scored_leads": 0}
    )
    repo.deal_kpi_metrics = AsyncMock(
        return_value={
            "pipeline_revenue": 0.0,
            "deals_won_amount": 0.0,
            "closed_deals": 0,
            "won_deals": 0,
        }
    )
    repo.financial_kpis = AsyncMock(return_value=FINANCIAL_KPIS)
    repo.get_organization_currency_locale = AsyncMock(return_value=("USD", "en-US"))
    repo.recent_leads = AsyncMock()
    service = _service_with(repo, SettingRepository())

    result = await service.get_kpis(AsyncMock(spec=AsyncSession), "org-1")

    assert result.recent_activity == []
    repo.recent_leads.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_sales_funnel_orders_standard_stages_first():
    repo: Any = DashboardRepository()
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
    setting_repo: Any = SettingRepository()
    setting_repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_custom_widgets(db, "org-1")

    assert len(result) == 9
    assert result[0]["id"] == "w-kpis"
    assert any(widget["id"] == "w-revenue" for widget in result)
    setting_repo.get_by_key.assert_awaited_once_with(db, "dashboard_custom_widgets:org-1:shared")


@pytest.mark.asyncio
async def test_get_custom_widgets_returns_defaults_for_corrupt_json():
    setting_repo: Any = SettingRepository()
    setting_repo.get_by_key = AsyncMock(return_value=SimpleNamespace(value="{not-json"))
    service = _service_with(DashboardRepository(), setting_repo)

    result = await service.get_custom_widgets(AsyncMock(spec=AsyncSession), "org-1")

    assert result == DashboardService.DEFAULT_WIDGETS


@pytest.mark.asyncio
async def test_get_custom_widgets_merges_legacy_preferences_with_new_defaults():
    setting_repo: Any = SettingRepository()
    setting_repo.get_by_key = AsyncMock(
        return_value=SimpleNamespace(
            value='[{"id":"w-kpis","title":"Executive KPIs","enabled":false}]'
        )
    )
    service = _service_with(DashboardRepository(), setting_repo)

    result = await service.get_custom_widgets(AsyncMock(spec=AsyncSession), "org-1")

    assert next(item for item in result if item["id"] == "w-kpis")["enabled"] is False
    assert next(item for item in result if item["id"] == "w-revenue")["enabled"] is True


@pytest.mark.asyncio
async def test_save_custom_widgets_persists_preferences():
    setting_repo: Any = SettingRepository()
    setting_repo.upsert = AsyncMock()
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.save_custom_widgets(db, "org-1", [{"id": "w-kpis", "enabled": True}])

    assert result["status"] == "success"
    setting_repo.upsert.assert_awaited_once_with(
        db,
        key="dashboard_custom_widgets:org-1:shared",
        value='[{"id": "w-kpis", "enabled": true}]',
    )


@pytest.mark.asyncio
async def test_save_custom_widgets_returns_generic_error_for_serialization_failure(monkeypatch):
    setting_repo: Any = SettingRepository()
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
    setting_repo: Any = SettingRepository()
    setting_repo.upsert = AsyncMock(side_effect=RuntimeError("database unavailable"))
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.save_custom_widgets(db, "org-1", [])

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_custom_widgets_rolls_back_commit_failure():
    setting_repo: Any = SettingRepository()
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
    repo: Any = DashboardRepository()
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
    assert repo.count_calls.await_args_list[-1].args[1] == "org-1"


@pytest.mark.asyncio
async def test_get_lead_conversions_merges_equivalent_urls():
    repo: Any = DashboardRepository()
    repo.lead_source_conversions = AsyncMock(
        return_value=[("https://Selv.in/", 2, 1), ("https://selv.in", 3, 2)]
    )
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_lead_conversions(db, "org-1")

    assert result == [{"source": "selv.in", "leads": 5, "converted": 3, "rate": 60.0}]
    repo.lead_source_conversions.assert_awaited_once_with(
        db, "org-1", None, start_at=None, end_at=None
    )


@pytest.mark.asyncio
async def test_get_recent_deals_uses_owner_name_and_updated_timestamp():
    repo: Any = DashboardRepository()
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

    statement = db.execute.await_args_list[-1].args[0]
    owner_join = statement.get_final_froms()[0]
    assert any(
        condition.compare(User.is_active.is_(True)) for condition in owner_join.onclause.clauses
    )


@pytest.mark.asyncio
async def test_recent_leads_excludes_archived_leads():
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    await DashboardRepository().recent_leads(db, "org-1")

    statement = db.execute.await_args_list[-1].args[0]
    assert any(
        condition.compare(Lead.organization_id == "org-1")
        for condition in statement._where_criteria
    )
    assert any(
        condition.compare(Lead.is_archived.is_(False)) for condition in statement._where_criteria
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
@pytest.mark.parametrize("stored_currency", ["$", "US Dollar", "   ", "USDX", "XYZ", None])
async def test_organization_currency_locale_falls_back_for_invalid_currency(stored_currency):
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.first.return_value = (stored_currency, "en-IN")
    db.execute.return_value = result

    currency, locale = await DashboardRepository().get_organization_currency_locale(db, "org-1")

    assert currency == "INR"
    assert locale == "en-IN"


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_locale", [None, "", "en_US", "abcd"])
async def test_organization_currency_locale_falls_back_for_invalid_locale(stored_locale):
    db = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.first.return_value = ("INR", stored_locale)
    db.execute.return_value = result

    currency, locale = await DashboardRepository().get_organization_currency_locale(db, "org-1")

    assert currency == "INR"
    assert locale == "en"


@pytest.mark.asyncio
async def test_ai_insight_includes_only_record_scoped_deal_context(monkeypatch):
    repo: Any = DashboardRepository()
    repo.count_leads = AsyncMock(return_value=1)
    repo.count_deals_and_sum = AsyncMock(return_value=(1, 5000.0))
    repo.get_organization_currency_locale = AsyncMock(return_value=("INR", "en-IN"))
    repo.top_deal = AsyncMock(
        return_value=SimpleNamespace(
            id="deal-1",
            title="Enterprise renewal",
            amount=5000.0,
            stage="Negotiation",
            probability=70.0,
            updated_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
    )
    ai_service = AsyncMock()
    ai_service.generate_dashboard_insights.return_value = {
        "summary": "One recorded deal is in negotiation.",
        "insights": [
            {
                "title": "Review enterprise renewal",
                "description": "The recorded deal remains in negotiation.",
                "type": "info",
                "action": "Review",
                "deal_id": "deal-1",
            }
        ],
        "risk_deals": [],
        "run_id": "run-1",
    }
    service = _service_with(repo, SettingRepository(), ai_service)
    actor = User(id="user-1", email="user@example.com", organization_id="org-1")
    db = AsyncMock(spec=AsyncSession)
    resolve_access = AsyncMock(side_effect=["lead-scope", "deal-scope"])
    monkeypatch.setattr(record_access_service, "resolve", resolve_access)

    result = await service.get_ai_insights(db, "org-1", actor)

    assert result["insights"][0]["deal_id"] == "deal-1"
    assert result["run_id"] == "run-1"
    assert DashboardAiInsightsResponse.model_validate(result).insights[0].deal_id == "deal-1"
    context = ai_service.generate_dashboard_insights.await_args.args[1]
    assert context["metrics"]["total_pipeline_amount"] == 5000.0
    assert context["deals"][0]["id"] == "deal-1"
    repo.count_leads.assert_awaited_once_with(db, "org-1", "lead-scope")
    repo.count_deals_and_sum.assert_awaited_once_with(db, "org-1", "deal-scope")
    repo.top_deal.assert_awaited_once_with(db, "org-1", "deal-scope")


@pytest.mark.asyncio
async def test_ai_insights_route_passes_platform_admin_selected_organization(monkeypatch):
    actor = User(
        id="platform-admin",
        email="admin@example.com",
        is_platform_admin=True,
    )
    actor._request_organization_id = "selected-org"
    get_ai_insights = AsyncMock(return_value={"summary": "", "insights": [], "risk_deals": []})
    monkeypatch.setattr(dashboard_router.dashboard_service, "get_ai_insights", get_ai_insights)
    db = AsyncMock(spec=AsyncSession)

    await dashboard_router.get_dashboard_ai_insights(db=db, current_user=actor)

    get_ai_insights.assert_awaited_once_with(db, "selected-org", actor)


def test_ai_insights_route_requires_deal_read_permission():
    route = next(
        item
        for item in dashboard_router.router.routes
        if isinstance(item, APIRoute) and item.path == "/ai-insights"
    )
    permissions = {
        cell.cell_contents
        for dependency in route.dependencies
        for cell in (dependency.dependency.__closure__ or ())  # type: ignore[union-attr]
        if isinstance(cell.cell_contents, str)
    }

    assert permissions == {"dashboard:read", "ai:generate", "deals:read"}


@pytest.mark.asyncio
async def test_revenue_chart_uses_closed_won_revenue_without_fabricating_targets():
    repo: Any = DashboardRepository()
    repo.monthly_won_revenue = AsyncMock(return_value=[(datetime(2026, 8, 1, tzinfo=UTC), 2500.0)])
    service = _service_with(repo, SettingRepository())
    start_at = datetime(2026, 8, 1, tzinfo=UTC)
    end_at = datetime(2026, 9, 1, tzinfo=UTC)

    result = await service.get_revenue_chart(
        AsyncMock(spec=AsyncSession),
        "org-1",
        start_at=start_at,
        end_at=end_at,
    )

    assert result == {"months": ["Aug 2026"], "actual": [2500.0], "target": []}


@pytest.mark.asyncio
async def test_revenue_chart_fills_months_without_won_revenue():
    repo: Any = DashboardRepository()
    repo.monthly_won_revenue = AsyncMock(
        return_value=[
            (datetime(2026, 7, 1, tzinfo=UTC), 1000.0),
            (datetime(2026, 9, 1, tzinfo=UTC), 3000.0),
        ]
    )
    service = _service_with(repo, SettingRepository())

    result = await service.get_revenue_chart(
        AsyncMock(spec=AsyncSession),
        "org-1",
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 10, 1, tzinfo=UTC),
    )

    assert result == {
        "months": ["Jul 2026", "Aug 2026", "Sep 2026"],
        "actual": [1000.0, 0.0, 3000.0],
        "target": [],
    }


def test_dashboard_date_range_requires_a_complete_ordered_pair():
    start_at = datetime(2026, 9, 1, tzinfo=UTC)
    end_at = datetime(2026, 10, 1, tzinfo=UTC)

    _validate_date_range(start_at, end_at)
    with pytest.raises(APIException) as missing_end:
        _validate_date_range(start_at, None)
    with pytest.raises(APIException) as reversed_range:
        _validate_date_range(end_at, start_at)

    assert missing_end.value.status_code == 422
    assert reversed_range.value.code == "INVALID_DATE_RANGE"


def test_custom_widget_request_rejects_malformed_payload():
    with pytest.raises(ValidationError):
        CustomWidgetSaveRequest.model_validate(
            {"id": "not-a-widget-id", "title": "KPIs", "enabled": "yes", "extra": True}
        )
