from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService, compute_next_run, today_str

TEST_HASH = "hash"


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, key):
        return self.__dict__[key]


def _make_user(org_id="org-1", user_id="user-1"):
    return User(
        id=user_id,
        email="test@crm.com",
        name="Test User",
        organization_id=org_id,
        role="Admin",
        hashed_password=TEST_HASH,
    )


@pytest.mark.asyncio
async def test_sales_performance_report_builds_rows_with_org():
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=150000.0)
    repo.rep_performance = AsyncMock(
        return_value=[
            ("user-1", "Alice", "AE", 10, 4, 60000.0),
            ("user-2", "Bob", "SE", 5, 1, 10000.0),
        ]
    )
    repo.quotas_by_user = AsyncMock(return_value={"user-1": 100000.0})
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-acme")

    result = await service.get_sales_performance_report(db, current_user=user)

    repo.total_won_revenue.assert_awaited_once_with(db, "org-acme")
    repo.rep_performance.assert_awaited_once_with(db, "org-acme")
    assert result["report_type"] == "Sales Performance"
    assert result["metrics"]["total_revenue"] == 150000.0
    assert len(result["metrics"]["table_rows"]) == 2
    assert result["metrics"]["table_rows"][0]["rep_name"] == "Alice"
    assert result["metrics"]["table_rows"][0]["win_rate"] == 40.0
    # Quota comes from persisted UserQuota records only.
    assert result["metrics"]["table_rows"][0]["quota_target"] == 100000.0
    assert result["metrics"]["table_rows"][0]["attainment_pct"] == 60.0
    # Rep without a configured quota must not get a fabricated one.
    assert result["metrics"]["table_rows"][1]["quota_target"] is None
    assert result["metrics"]["table_rows"][1]["attainment_pct"] is None
    assert result["metrics"]["monthly_target"] == 100000.0


@pytest.mark.asyncio
async def test_pipeline_velocity_empty_returns_zero_avg():
    repo: Any = ReportRepository()
    repo.stage_age_breakdown = AsyncMock(return_value=[])
    repo.closed_cycle_stats = AsyncMock(
        return_value=Row(closed_cnt=0, fastest_sec=0.0, longest_sec=0.0, avg_sec=0.0)
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_pipeline_velocity_report(db, current_user=user)

    assert result["metrics"]["avg_days_to_close"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_financial_overview_separates_booked_and_collected_values():
    repo: Any = ReportRepository()
    repo.financial_overview = AsyncMock(
        return_value={
            "pipeline_value": 50000.0,
            "booked_value": 25000.0,
            "quote_count": 2,
            "quoted_value": 24000.0,
            "accepted_quote_value": 20000.0,
            "invoice_count": 1,
            "invoiced_value": 20000.0,
            "invoice_paid_value": 12000.0,
            "outstanding_amount": 8000.0,
            "overdue_amount": 0.0,
            "payment_count": 1,
            "collected_revenue": 12000.0,
        }
    )
    repo.invoice_status_breakdown = AsyncMock(
        return_value=[Row(status="Pending", invoice_count=1, invoice_value=20000, paid_value=12000)]
    )
    repo.organization_currency = AsyncMock(return_value="INR")
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-finance")

    result = await service.get_financial_overview_report(db, current_user=user)

    repo.financial_overview.assert_awaited_once_with(db, "org-finance")
    repo.invoice_status_breakdown.assert_awaited_once_with(db, "org-finance")
    assert result["metrics"]["booked_value"] == 25000.0
    assert result["metrics"]["collected_revenue"] == 12000.0
    assert result["metrics"]["outstanding_amount"] == 8000.0
    assert result["metrics"]["currency"] == "INR"
    assert result["metrics"]["table_rows"][0]["outstanding_amount"] == 8000.0


@pytest.mark.asyncio
async def test_quote_conversion_uses_persisted_quote_and_invoice_counts():
    repo: Any = ReportRepository()
    repo.quote_status_breakdown = AsyncMock(
        return_value=[
            Row(status="Sent", quote_count=2, quote_value=30000),
            Row(status="Accepted", quote_count=1, quote_value=20000),
        ]
    )
    repo.quote_conversion_counts = AsyncMock(return_value=(1, 1))
    repo.organization_currency = AsyncMock(return_value="INR")
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-quotes")

    result = await service.get_quote_conversion_report(db, current_user=user)

    assert result["metrics"]["total_quotes"] == 3
    assert result["metrics"]["quote_acceptance_rate"] == 33.3
    assert result["metrics"]["quote_to_invoice_rate"] == 100.0


@pytest.mark.asyncio
async def test_pipeline_velocity_computes_real_stage_age():
    repo: Any = ReportRepository()
    repo.stage_age_breakdown = AsyncMock(return_value=[("Negotiation", 2, 30000.0, 5 * 86400.0)])
    repo.closed_cycle_stats = AsyncMock(
        return_value=Row(
            closed_cnt=3, fastest_sec=2 * 86400.0, longest_sec=20 * 86400.0, avg_sec=10 * 86400.0
        )
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_pipeline_velocity_report(db, current_user=user)

    row = result["metrics"]["table_rows"][0]
    assert row["avg_days_in_stage"] == 5.0
    assert row["bottleneck_risk"] == "Medium"
    assert "conversion_rate" not in row  # fabricated metric removed
    assert result["metrics"]["avg_days_to_close"] == 10.0
    assert result["metrics"]["closed_won_deals"] == 3


@pytest.mark.asyncio
async def test_win_loss_report_ratio():
    repo: Any = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(side_effect=[7, 3])
    repo.win_loss_by_industry = AsyncMock(return_value=[("Software", 5, 1, 50000.0, 5000.0)])
    repo.top_loss_reason = AsyncMock(return_value="Budget Constraint")
    repo.loss_reason_by_industry = AsyncMock(
        return_value=[
            ("Software", "Missing champion", 2),
            ("Software", "Budget Constraint", 3),
        ]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_win_loss_report(db, current_user=user)

    assert result["metrics"]["win_percentage"] == 70.0
    assert result["metrics"]["loss_percentage"] == 30.0
    assert result["metrics"]["total_won_deals"] == 7
    assert result["metrics"]["top_loss_reason"] == "Budget Constraint"
    assert result["metrics"]["table_rows"][0]["segment"] == "Software"
    # Industry row reports its own modal reason, not the org-wide one.
    assert result["metrics"]["table_rows"][0]["primary_loss_reason"] == "Budget Constraint"


@pytest.mark.asyncio
async def test_win_loss_industry_reasons_are_not_copied_across_segments():
    repo: Any = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(side_effect=[1, 1])
    repo.top_loss_reason = AsyncMock(return_value="Budget Constraint")
    repo.win_loss_by_industry = AsyncMock(
        return_value=[("Manufacturing", 1, 0, 100.0, 0.0), ("Retail", 0, 1, 0.0, 50.0)]
    )
    repo.loss_reason_by_industry = AsyncMock(return_value=[("Retail", "Pricing", 1)])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_win_loss_report(db, current_user=user)

    rows = {r["segment"]: r for r in result["metrics"]["table_rows"]}
    # Manufacturing has no recorded reasons: must be null, never another
    # industry's (or the org-wide) reason.
    assert rows["Manufacturing"]["primary_loss_reason"] is None
    assert rows["Retail"]["primary_loss_reason"] == "Pricing"


@pytest.mark.asyncio
async def test_win_loss_report_without_recorded_reasons():
    repo: Any = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(side_effect=[7, 3])
    repo.win_loss_by_industry = AsyncMock(return_value=[])
    repo.top_loss_reason = AsyncMock(return_value=None)
    repo.loss_reason_by_industry = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_win_loss_report(db, current_user=user)

    assert result["metrics"]["top_loss_reason"] is None


@pytest.mark.asyncio
async def test_lead_attribution_has_no_fabricated_revenue():
    repo: Any = ReportRepository()
    repo.leads_by_source = AsyncMock(return_value=[("Website", 10, 4, 72.0)])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_lead_attribution_report(db, current_user=user)

    row = result["metrics"]["table_rows"][0]
    assert row["total_leads"] == 10
    assert row["converted_leads"] == 4
    assert row["conversion_rate"] == 40.0
    for fabricated in ("revenue_generated", "cac", "roi_ratio"):
        assert fabricated not in row


@pytest.mark.asyncio
async def test_rep_leaderboard_uses_real_quota_and_no_activity_padding():
    repo: Any = ReportRepository()
    repo.rep_leaderboard = AsyncMock(
        return_value=[("user-1", "Alice", "a@x.com", "AE", 6, 120000.0)]
    )
    repo.quotas_by_user = AsyncMock(return_value={"user-1": 100000.0})
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_rep_leaderboard_report(db, current_user=user)

    row = result["metrics"]["table_rows"][0]
    assert row["rank"] == 1
    assert row["badge"] == "Top Performer"
    assert row["quota_target"] == 100000.0
    assert row["attainment_pct"] == 120.0
    for fabricated in ("calls_made", "meetings_held"):
        assert fabricated not in row


@pytest.mark.asyncio
async def test_revenue_forecast_periods_from_expected_close_dates():
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=80000.0)
    repo.revenue_forecast = AsyncMock(return_value=Row(total_pipeline=50000.0, weighted=25000.0))
    repo.forecast_by_period = AsyncMock(
        return_value=[("2026-Q3", 2, 20000.0, 10000.0), ("2026-Q4", 3, 30000.0, 15000.0)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_revenue_forecasting_report(db, current_user=user)

    metrics = result["metrics"]
    assert metrics["committed_revenue"] == 80000.0
    assert metrics["open_pipeline_amount"] == 50000.0
    assert metrics["weighted_pipeline_amount"] == 25000.0
    assert [r["period"] for r in metrics["table_rows"]] == ["2026-Q3", "2026-Q4"]
    for fabricated in ("q3_predicted", "q4_predicted", "confidence"):
        assert fabricated not in metrics


@pytest.mark.asyncio
async def test_revenue_forecast_no_pipeline():
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=0.0)
    repo.revenue_forecast = AsyncMock(return_value=None)
    repo.forecast_by_period = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_revenue_forecasting_report(db, current_user=user)

    assert result["metrics"]["committed_revenue"] == 0.0
    assert result["metrics"]["open_pipeline_amount"] == 0.0
    assert result["metrics"]["weighted_pipeline_amount"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_activity_metrics_org_totals_only():
    repo: Any = ReportRepository()
    repo.count_calls = AsyncMock(return_value=12)
    repo.total_call_duration_seconds = AsyncMock(return_value=3600)
    repo.count_emails = AsyncMock(return_value=40)
    repo.count_opened_emails = AsyncMock(return_value=10)
    repo.count_meetings = AsyncMock(return_value=5)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_activity_metrics_report(db, current_user=user)

    metrics = result["metrics"]
    assert metrics["total_calls"] == 12
    assert metrics["total_call_duration_minutes"] == 60.0
    assert metrics["total_emails"] == 40
    assert metrics["email_open_rate_pct"] == 25.0
    assert metrics["total_meetings"] == 5
    # No per-rep attribution columns exist in the schema: rows stay empty.
    assert metrics["table_rows"] == []


@pytest.mark.asyncio
async def test_deal_duration_computes_real_cycle_stats():
    repo: Any = ReportRepository()
    repo.closed_cycle_stats = AsyncMock(
        return_value=Row(
            closed_cnt=4, fastest_sec=2 * 86400.0, longest_sec=30 * 86400.0, avg_sec=12.5 * 86400.0
        )
    )
    repo.stage_age_breakdown = AsyncMock(return_value=[("Proposal", 3, 40000.0, 21 * 86400.0)])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_deal_duration_report(db, current_user=user)

    metrics = result["metrics"]
    assert metrics["avg_cycle_days"] == 12.5
    assert metrics["fastest_close_days"] == 2.0
    assert metrics["longest_close_days"] == 30.0
    assert metrics["closed_won_deals"] == 4
    assert metrics["table_rows"][0]["primary_bottleneck"] == "Proposal (avg 21.0d)"


@pytest.mark.asyncio
async def test_deal_duration_empty_when_nothing_closed():
    repo: Any = ReportRepository()
    repo.closed_cycle_stats = AsyncMock(
        return_value=Row(closed_cnt=0, fastest_sec=0.0, longest_sec=0.0, avg_sec=0.0)
    )
    repo.stage_age_breakdown = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_deal_duration_report(db, current_user=user)

    assert result["metrics"]["avg_cycle_days"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_cac_is_unavailable_without_marketing_spend():
    repo: Any = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(return_value=8)
    repo.total_won_revenue = AsyncMock(return_value=200000.0)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_cac_report(db, current_user=user)

    metrics = result["metrics"]
    assert metrics["available"] is False
    assert "spend" in metrics["reason"]
    assert metrics["table_rows"] == []
    repo.count_deals_in_stage.assert_not_awaited()
    repo.total_won_revenue.assert_not_awaited()


@pytest.mark.asyncio
async def test_ltv_is_unavailable_without_customer_payment_history():
    repo: Any = ReportRepository()
    repo.won_aggregate = AsyncMock(return_value=(5, 300000.0))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_ltv_report(db, current_user=user)

    metrics = result["metrics"]
    assert metrics["available"] is False
    assert "payment history" in metrics["reason"]
    assert metrics["table_rows"] == []
    repo.won_aggregate.assert_not_awaited()


@pytest.mark.asyncio
async def test_churn_is_unavailable_without_subscription_lifecycle():
    repo: Any = ReportRepository()
    repo.lost_aggregate = AsyncMock(return_value=(2, 20000.0))
    repo.count_deals = AsyncMock(return_value=10)
    repo.top_loss_reason = AsyncMock(return_value="Pricing")
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_churn_analysis_report(db, current_user=user)

    assert result["metrics"]["available"] is False
    assert "Closed Lost deals are not churn" in result["metrics"]["reason"]
    assert result["metrics"]["table_rows"] == []
    repo.lost_aggregate.assert_not_awaited()
    repo.count_deals.assert_not_awaited()
    repo.top_loss_reason.assert_not_awaited()


@pytest.mark.asyncio
async def test_quota_attainment_with_and_without_quotas():
    repo: Any = ReportRepository()
    repo.rep_quota = AsyncMock(
        return_value=[
            ("user-1", "Alice", "AE", 90000.0, 50000.0),
            ("user-2", "Bob", "SE", 20000.0, 30000.0),
        ]
    )
    repo.quotas_by_user = AsyncMock(return_value={"user-1": 100000.0})
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.get_quota_attainment_report(db, current_user=user)

    rows = result["metrics"]["table_rows"]
    assert rows[0]["attainment_pct"] == 90.0
    assert rows[0]["status"] == "On Track"
    assert rows[1]["assigned_quota"] is None
    assert rows[1]["status"] == "No Quota Set"
    # Team attainment counts only reps with a configured quota.
    assert result["metrics"]["team_attainment_pct"] == 90.0
    assert result["metrics"]["reps_with_quota"] == 1


@pytest.mark.asyncio
async def test_list_custom_reports_uses_today_fallback():
    repo: Any = ReportRepository()
    repo.list_custom_reports = AsyncMock(
        return_value=[
            Row(id="r1", name="Q3", filters=None, metrics_included="a,b", created_at=None)
        ]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.list_custom_reports(db, current_user=user)

    assert result[0]["filters"] == "All Accounts"
    assert result[0]["metrics_included"] == ["a", "b"]
    assert result[0]["created_at"] == today_str()


@pytest.mark.asyncio
async def test_create_custom_report_validates_and_commits():
    repo: Any = ReportRepository()
    repo.create_custom_report = AsyncMock(return_value=Row(id="r1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-target")

    result = await service.create_custom_report(db, "My Report", "filter_x", current_user=user)

    assert repo.create_custom_report.await_args is not None
    data = repo.create_custom_report.await_args_list[-1].kwargs["data"]
    assert data["organization_id"] == "org-target"
    assert data["name"] == "My Report"
    assert data["filters"] == "filter_x"
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_custom_report_empty_name_raises():
    repo: Any = ReportRepository()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    with pytest.raises(APIException) as exc_info:
        await service.create_custom_report(db, "   ", current_user=user)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_run_custom_report_found():
    repo: Any = ReportRepository()
    repo.get_custom_report = AsyncMock(
        return_value=Row(
            id="r1",
            name="Enterprise Deals",
            filters="All Enterprise Filters",
            metrics_included="sales-performance",
        )
    )
    repo.total_won_revenue = AsyncMock(return_value=50000.0)
    repo.count_deals = AsyncMock(return_value=12)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.run_custom_report(db, "r1", current_user=user)

    assert result["report_type"] == "Enterprise Deals"
    assert result["metrics"]["total_revenue"] == 50000.0
    assert result["metrics"]["deals_analyzed"] == 12


@pytest.mark.asyncio
async def test_run_custom_report_not_found_raises_404():
    repo: Any = ReportRepository()
    repo.get_custom_report = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    with pytest.raises(NotFoundError):
        await service.run_custom_report(db, "missing", current_user=user)


@pytest.mark.asyncio
async def test_delete_custom_report_not_found_raises_404():
    repo: Any = ReportRepository()
    repo.get_custom_report = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    with pytest.raises(NotFoundError):
        await service.delete_custom_report(db, "missing", current_user=user)


@pytest.mark.asyncio
async def test_delete_custom_report_success():
    repo: Any = ReportRepository()
    mock_report = Row(id="r1", name="Report 1")
    repo.get_custom_report = AsyncMock(return_value=mock_report)
    repo.delete_custom_report = AsyncMock()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.delete_custom_report(db, "r1", current_user=user)

    repo.delete_custom_report.assert_awaited_once_with(db, mock_report)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_schedule_report_email_validations():
    repo: Any = ReportRepository()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    # Invalid email
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(
            db, "sales-performance", "not-an-email", "Weekly", current_user=user
        )
    assert exc.value.status_code == 422

    # Invalid frequency
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(
            db, "sales-performance", "valid@email.com", "Yearly", current_user=user
        )
    assert exc.value.status_code == 422

    # Invalid report type
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(
            db, "invalid-type", "valid@email.com", "Weekly", current_user=user
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_schedule_report_email_sets_next_run():
    repo: Any = ReportRepository()
    repo.create_scheduled_report = AsyncMock(return_value=Row(id="s1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-custom")

    result = await service.schedule_report_email(
        db, "sales-performance", "lead@company.com", "Daily", current_user=user
    )

    assert repo.create_scheduled_report.await_args is not None
    data = repo.create_scheduled_report.await_args_list[-1].kwargs["data"]
    assert data["organization_id"] == "org-custom"
    assert data["email"] == "lead@company.com"
    assert data["frequency"] == "Daily"
    assert data["next_run"] is not None
    assert result["message"].startswith("Scheduled Daily")


@pytest.mark.asyncio
async def test_delete_scheduled_report():
    repo: Any = ReportRepository()
    mock_sched = Row(id="s1")
    repo.get_scheduled_report = AsyncMock(return_value=mock_sched)
    repo.delete_scheduled_report = AsyncMock()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    result = await service.delete_scheduled_report(db, "s1", current_user=user)

    repo.delete_scheduled_report.assert_awaited_once_with(db, mock_sched)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_resolve_org_id_strict_isolation():
    repo: Any = ReportRepository()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    # Missing user -> ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.get_sales_performance_report(db, current_user=None)

    # User without organization_id -> ForbiddenError
    user_no_org = _make_user(org_id="")
    with pytest.raises(ForbiddenError):
        await service.get_sales_performance_report(db, current_user=user_no_org)

    # Mismatched org_id -> ForbiddenError
    user = _make_user(org_id="org-1")
    with pytest.raises(ForbiddenError):
        await service.get_sales_performance_report(db, org_id="org-other", current_user=user)


@pytest.mark.asyncio
async def test_list_custom_reports_pagination():
    repo: Any = ReportRepository()
    repo.list_custom_reports = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-test")

    await service.list_custom_reports(db, current_user=user, limit=15, offset=30)
    repo.list_custom_reports.assert_awaited_once_with(db, "org-test", limit=15, offset=30)


@pytest.mark.asyncio
async def test_list_scheduled_reports_pagination():
    repo: Any = ReportRepository()
    repo.list_scheduled_reports = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-test")

    await service.list_scheduled_reports(db, current_user=user, limit=25, offset=50)
    repo.list_scheduled_reports.assert_awaited_once_with(db, "org-test", limit=25, offset=50)


@pytest.mark.asyncio
async def test_export_report_pdf_validates_type_and_user(monkeypatch):
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=25000.0)
    repo.rep_performance = AsyncMock(return_value=[("user-1", "Alice", "AE", 4, 1, 25000.0)])
    repo.quotas_by_user = AsyncMock(return_value={})
    repo.create_export = AsyncMock(
        return_value=Row(
            id="exp-1",
            download_url=None,
            s3_key="exports/org-sales/abc123.pdf",
        )
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-sales", user_id="usr-alex")

    monkeypatch.setattr(
        "app.services.report_service.s3_service.upload_file",
        lambda *a, **kw: "exports/org-sales/abc123.pdf",
    )
    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example.com/exports/test.pdf",
    )

    result = await service.export_report_pdf(db, "sales-performance", current_user=user)

    assert repo.create_export.await_args is not None
    data = repo.create_export.await_args_list[-1].kwargs["data"]
    assert data["organization_id"] == "org-sales"
    assert data["requested_by"] == "usr-alex"
    assert data["file_format"] == "pdf"
    assert data["download_url"] is None  # never persist presigned URL
    assert data["s3_key"].startswith("exports/org-sales/")
    assert len(data["s3_key"]) <= 1024  # fits varchar(1024)
    assert "pdf_url" in result
    assert result["export_id"] == "exp-1"


@pytest.mark.asyncio
async def test_export_report_pdf_accepts_enum_report_type(monkeypatch):
    from app.schemas.report_schemas import ReportTypeEnum

    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=0.0)
    repo.rep_performance = AsyncMock(return_value=[])
    repo.quotas_by_user = AsyncMock(return_value={})
    repo.create_export = AsyncMock(return_value=Row(id="exp-2", download_url=None, s3_key="k"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-enum")

    monkeypatch.setattr(
        "app.services.report_service.s3_service.upload_file", lambda *a, **kw: "exports/k.pdf"
    )
    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example/x",
    )

    result = await service.export_report_pdf(
        db, ReportTypeEnum.SALES_PERFORMANCE, current_user=user
    )
    assert repo.create_export.await_args is not None
    data = repo.create_export.await_args_list[-1].kwargs["data"]
    assert data["report_type"] == "sales-performance"
    assert "pdf_url" in result


def test_today_str_format():
    value = today_str()
    assert len(value) == 10
    assert "-" in value


def test_compute_next_run_daily_and_weekly():
    base = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    daily = compute_next_run("Daily", base)
    assert daily == datetime(2026, 3, 11, 12, 0, tzinfo=UTC)

    weekly = compute_next_run("Weekly", base)
    assert weekly == datetime(2026, 3, 17, 12, 0, tzinfo=UTC)


def test_compute_next_run_monthly_calendar_arithmetic():
    # Jan 31 -> Feb 28 (clamps to last day of Feb)
    jan31 = datetime(2026, 1, 31, 10, 0, tzinfo=UTC)
    feb_run = compute_next_run("Monthly", jan31)
    assert feb_run.year == 2026
    assert feb_run.month == 2
    assert feb_run.day == 28

    # Dec 15 -> Jan 15 of next year
    dec15 = datetime(2026, 12, 15, 10, 0, tzinfo=UTC)
    jan_run = compute_next_run("Monthly", dec15)
    assert jan_run.year == 2027
    assert jan_run.month == 1
    assert jan_run.day == 15


@pytest.mark.asyncio
async def test_export_report_pdf_raises_on_commit_failure(monkeypatch):
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=0.0)
    repo.rep_performance = AsyncMock(return_value=[])
    repo.quotas_by_user = AsyncMock(return_value={})
    repo.create_export = AsyncMock(
        return_value=Row(id="exp-pdf", download_url=None, s3_key="exports/test.pdf")
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("DB connection lost")
    user = _make_user(org_id="org-fail", user_id="usr-1")

    monkeypatch.setattr(
        "app.services.report_service.s3_service.upload_file", lambda *a, **kw: "exports/test.pdf"
    )
    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example.com/test.pdf",
    )
    delete_file = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.report_service._cleanup_export_object",
        delete_file,
    )

    with pytest.raises(APIException) as exc_info:
        await service.export_report_pdf(db, "sales-performance", current_user=user)
    assert exc_info.value.status_code == 500
    delete_file.assert_awaited_once_with("exports/test.pdf")


@pytest.mark.asyncio
async def test_export_report_csv_sanitizes_formula_prefixes(monkeypatch):
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=7000.0)
    repo.rep_performance = AsyncMock(
        return_value=[
            ("user-1", "=cmd|' /C calc'!A0", "@Role", 5, 1, 5000.0),
            ("user-2", "+1234567890", "-StageMinus", 2, 0, 2000.0),
        ]
    )
    repo.quotas_by_user = AsyncMock(return_value={})
    repo.create_export = AsyncMock(
        return_value=Row(id="exp-csv", download_url=None, s3_key="exports/org-safe/x.csv")
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-safe", user_id="usr-1")

    uploaded = {}

    def fake_upload(file_obj, object_name="", content_type=None):
        uploaded["content"] = file_obj.read().decode("utf-8")
        return "exports/org-safe/x.csv"

    monkeypatch.setattr("app.services.report_service.s3_service.upload_file", fake_upload)
    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example.com/exports/csv.csv",
    )

    result = await service.export_report_csv(db, "sales-performance", current_user=user)

    assert repo.create_export.await_args is not None
    data = repo.create_export.await_args_list[-1].kwargs["data"]
    assert data["download_url"] is None  # never persist presigned URL
    assert data["s3_key"].startswith("exports/org-safe/")
    assert "csv_url" in result
    assert result["export_id"] == "exp-csv"
    # Dangerous formula prefixes are escaped; numeric negatives are preserved.
    assert "'=cmd" in uploaded["content"]
    assert "'+1234567890" in uploaded["content"]


@pytest.mark.asyncio
async def test_export_csv_reflects_requested_report_rows(monkeypatch):
    repo: Any = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(side_effect=[7, 3])
    repo.win_loss_by_industry = AsyncMock(return_value=[("Software", 5, 1, 50000.0, 5000.0)])
    repo.top_loss_reason = AsyncMock(return_value="Budget Constraint")
    repo.loss_reason_by_industry = AsyncMock(return_value=[])
    repo.create_export = AsyncMock(
        return_value=Row(id="exp-wl", download_url=None, s3_key="exports/org-1/x.csv")
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1", user_id="usr-1")

    uploaded = {}

    def fake_upload(file_obj, object_name="", content_type=None):
        uploaded["content"] = file_obj.read().decode("utf-8")
        return "exports/org-1/x.csv"

    monkeypatch.setattr("app.services.report_service.s3_service.upload_file", fake_upload)
    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example/x.csv",
    )

    result = await service.export_report_csv(db, "win-loss-ratio", current_user=user)

    # CSV must contain the win/loss breakdown, not raw deal rows.
    assert '"Software"' in uploaded["content"]
    assert '"win_percentage"' in uploaded["content"]
    assert "50000.0" in uploaded["content"]
    assert "csv_url" in result


@pytest.mark.asyncio
async def test_build_report_csv_for_organization_internal(monkeypatch):
    """Scheduler path: builds report data for an org without a request user."""
    repo: Any = ReportRepository()
    repo.leads_by_source = AsyncMock(return_value=[("Referral", 4, 2, 80.0)])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    csv_text = await service.build_report_csv_for_organization(db, "org-bg", "lead-attribution")

    assert '"source"' in csv_text
    assert '"Referral"' in csv_text
    repo.leads_by_source.assert_awaited_once_with(db, "org-bg")


@pytest.mark.asyncio
async def test_build_report_csv_for_organization_invalid_type():
    service = ReportService(repository=ReportRepository())
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.build_report_csv_for_organization(db, "org-bg", "not-a-type")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_export_report_csv_raises_502_on_s3_error(monkeypatch):
    repo: Any = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=0.0)
    repo.rep_performance = AsyncMock(return_value=[])
    repo.quotas_by_user = AsyncMock(return_value={})
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("S3 timeout")

    monkeypatch.setattr("app.services.report_service.s3_service.upload_file", boom)

    user = _make_user()
    with pytest.raises(APIException) as exc_info:
        await service.export_report_csv(db, "sales-performance", current_user=user)
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_get_export_download_mints_fresh_presigned_url(monkeypatch):
    repo: Any = ReportRepository()
    repo.get_export = AsyncMock(
        return_value=Row(id="exp-1", organization_id="org-1", s3_key="exports/org-1/abc.pdf")
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    monkeypatch.setattr(
        "app.services.report_service.s3_service.generate_presigned_url",
        lambda key: f"https://fresh.example/{key}?sig=new",
    )

    result = await service.get_export_download(db, export_id="exp-1", current_user=user)

    repo.get_export.assert_awaited_once_with(db, "exp-1", "org-1")
    assert result["download_url"] == "https://fresh.example/exports/org-1/abc.pdf?sig=new"
    assert result["expires_in"] == 3600


@pytest.mark.asyncio
async def test_get_export_download_cross_org_not_found():
    repo: Any = ReportRepository()
    repo.get_export = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-A")

    with pytest.raises(NotFoundError):
        await service.get_export_download(db, export_id="exp-from-org-B", current_user=user)

    repo.get_export.assert_awaited_once_with(db, "exp-from-org-B", "org-A")


@pytest.mark.asyncio
async def test_get_export_download_legacy_record_without_s3_key_returns_410(monkeypatch):
    repo: Any = ReportRepository()
    repo.get_export = AsyncMock(
        return_value=Row(
            id="exp-legacy",
            organization_id="org-1",
            s3_key=None,
            download_url="https://expired.example/old?sig=expired",
        )
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-1")

    def boom(*args, **kwargs):
        raise AssertionError("presigned URL must not be minted for legacy records")

    monkeypatch.setattr("app.services.report_service.s3_service.generate_presigned_url", boom)

    with pytest.raises(APIException) as exc:
        await service.get_export_download(db, export_id="exp-legacy", current_user=user)
    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_get_export_download_raises_502_when_s3_fails(monkeypatch):
    repo: Any = ReportRepository()
    repo.get_export = AsyncMock(
        return_value=Row(id="exp-1", organization_id="org-1", s3_key="exports/org-1/abc.pdf")
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr("app.services.report_service.s3_service.generate_presigned_url", boom)

    with pytest.raises(APIException) as exc:
        await service.get_export_download(db, export_id="exp-1", current_user=_make_user())
    assert exc.value.status_code == 502


# --- CSV sanitization: negative numbers preserved, formulas escaped ---


@pytest.mark.parametrize(
    "value,expected",
    [
        ("-123", "-123"),
        ("-123.45", "-123.45"),
        ("-0.001", "-0.001"),
        ("-1e10", "-1e10"),
        ("-123 text", "'-123 text"),
        ("=-123", "'=-123"),
        ("=SUM(A1:A2)", "'=SUM(A1:A2)"),
        ("+CMD(...)", "'+CMD(...)"),
        ("@formula", "'@formula"),
        ("normal text", "normal text"),
        ("hello, world", "hello, world"),
        ('say "hi"', 'say "hi"'),
        ("", ""),
        (None, ""),
        ("-", "'-"),
        ("- 5", "'- 5"),
    ],
)
def test_sanitize_csv_cell_negative_numeric_and_injection(value, expected):
    assert ReportService._sanitize_csv_cell(value) == expected
