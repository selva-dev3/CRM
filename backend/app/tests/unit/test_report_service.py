from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService, today_str


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, key):
        return self.__dict__[key]


@pytest.mark.asyncio
async def test_sales_performance_report_builds_rows():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.total_won_revenue = AsyncMock(return_value=150000.0)
    repo.rep_performance = AsyncMock(
        return_value=[("Alice", "AE", 10, 4, 60000.0), ("Bob", "SE", 5, 1, 10000.0)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_sales_performance_report(db)

    assert result["report_type"] == "Sales Performance"
    assert result["metrics"]["total_revenue"] == 150000.0
    assert len(result["metrics"]["table_rows"]) == 2
    assert result["metrics"]["table_rows"][0]["rep_name"] == "Alice"
    assert result["metrics"]["table_rows"][0]["win_rate"] == 40.0
    assert result["metrics"]["monthly_target"] == 200000.0


@pytest.mark.asyncio
async def test_pipeline_velocity_empty_returns_zero_avg():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.deals_by_stage = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_pipeline_velocity_report(db)

    assert result["metrics"]["avg_days_to_close"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_win_loss_report_ratio():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.count_deals_in_stage = AsyncMock(side_effect=[7, 3])
    repo.win_loss_by_industry = AsyncMock(
        return_value=[("Software", 5, 1, 50000.0, 5000.0)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_win_loss_report(db)

    assert result["metrics"]["win_percentage"] == 70.0
    assert result["metrics"]["loss_percentage"] == 30.0
    assert result["metrics"]["total_won_deals"] == 7
    assert result["metrics"]["table_rows"][0]["segment"] == "Software"


@pytest.mark.asyncio
async def test_revenue_forecast_no_pipeline():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.revenue_forecast = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_revenue_forecasting_report(db)

    assert result["metrics"]["q3_predicted"] == 0.0
    assert result["metrics"]["confidence"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_churn_analysis():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.lost_aggregate = AsyncMock(return_value=(2, 20000.0))
    repo.count_deals = AsyncMock(return_value=10)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_churn_analysis_report(db)

    assert result["metrics"]["annual_churn_rate"] == 20.0
    assert result["metrics"]["net_revenue_retention"] == 80.0
    assert result["metrics"]["table_rows"][0]["churned_accounts"] == 2


@pytest.mark.asyncio
async def test_list_custom_reports_uses_today_fallback():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.list_custom_reports = AsyncMock(
        return_value=[Row(id="r1", name="Q3", filters=None, metrics_included="a,b", created_at=None)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_custom_reports(db)

    assert result[0]["filters"] == "All Accounts"
    assert result[0]["metrics_included"] == ["a", "b"]
    assert result[0]["created_at"] == today_str()


@pytest.mark.asyncio
async def test_create_custom_report_commits(monkeypatch):
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.create_custom_report = AsyncMock(return_value=Row(id="r1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_custom_report(db, "My Report")

    data = repo.create_custom_report.await_args.kwargs["data"]
    assert data["name"] == "My Report"
    assert data["filters"] == "All Enterprise Filters"
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_custom_report_missing_report_uses_fallback_name():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.get_custom_report = AsyncMock(return_value=None)
    repo.total_won_revenue = AsyncMock(return_value=5000.0)
    repo.count_deals = AsyncMock(return_value=3)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.run_custom_report(db, "missing")

    assert result["report_type"] == "Custom Report (missing)"
    assert result["metrics"]["total_revenue"] == 5000.0


@pytest.mark.asyncio
async def test_schedule_report_email_sets_next_run():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.create_scheduled_report = AsyncMock(return_value=Row(id="s1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.schedule_report_email(db, "sales-performance", "a@b.com", "Weekly")

    data = repo.create_scheduled_report.await_args.kwargs["data"]
    assert data["email"] == "a@b.com"
    assert data["frequency"] == "Weekly"
    assert "report_type" in data
    assert result["message"].startswith("Scheduled Weekly")


@pytest.mark.asyncio
async def test_quota_attainment_statuses():
    repo = ReportRepository()
    repo.get_org_id = AsyncMock(return_value="org-1")
    repo.rep_quota = AsyncMock(
        return_value=[("A", "AE", 120000.0, 130000.0), ("B", "SE", 85000.0, 90000.0), ("C", "SDR", 50000.0, 60000.0)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_quota_attainment_report(db)

    rows = result["metrics"]["table_rows"]
    assert rows[0]["status"] == "Target Met"
    assert rows[1]["status"] == "On Track"
    assert rows[2]["status"] == "At Risk"
    assert result["metrics"]["team_attainment_pct"] == 85.0


def test_today_str_format():
    value = today_str()
    assert len(value) == 10
    assert "-" in value