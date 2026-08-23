from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models.user import User
from app.repositories.report_repository import ReportRepository
from app.services.report_service import ReportService, compute_next_run, today_str


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
        hashed_password="hash",
    )


@pytest.mark.asyncio
async def test_sales_performance_report_builds_rows_with_org():
    repo = ReportRepository()
    repo.total_won_revenue = AsyncMock(return_value=150000.0)
    repo.rep_performance = AsyncMock(
        return_value=[("Alice", "AE", 10, 4, 60000.0), ("Bob", "SE", 5, 1, 10000.0)]
    )
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
    assert result["metrics"]["monthly_target"] == 200000.0


@pytest.mark.asyncio
async def test_pipeline_velocity_empty_returns_zero_avg():
    repo = ReportRepository()
    repo.deals_by_stage = AsyncMock(return_value=[])
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_pipeline_velocity_report(db, org_id="org-1")

    assert result["metrics"]["avg_days_to_close"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_win_loss_report_ratio():
    repo = ReportRepository()
    repo.count_deals_in_stage = AsyncMock(side_effect=[7, 3])
    repo.win_loss_by_industry = AsyncMock(
        return_value=[("Software", 5, 1, 50000.0, 5000.0)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_win_loss_report(db, org_id="org-1")

    assert result["metrics"]["win_percentage"] == 70.0
    assert result["metrics"]["loss_percentage"] == 30.0
    assert result["metrics"]["total_won_deals"] == 7
    assert result["metrics"]["table_rows"][0]["segment"] == "Software"


@pytest.mark.asyncio
async def test_revenue_forecast_no_pipeline():
    repo = ReportRepository()
    repo.revenue_forecast = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_revenue_forecasting_report(db, org_id="org-1")

    assert result["metrics"]["q3_predicted"] == 0.0
    assert result["metrics"]["confidence"] == 0.0
    assert result["metrics"]["table_rows"] == []


@pytest.mark.asyncio
async def test_churn_analysis():
    repo = ReportRepository()
    repo.lost_aggregate = AsyncMock(return_value=(2, 20000.0))
    repo.count_deals = AsyncMock(return_value=10)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_churn_analysis_report(db, org_id="org-1")

    assert result["metrics"]["annual_churn_rate"] == 20.0
    assert result["metrics"]["net_revenue_retention"] == 80.0
    assert result["metrics"]["table_rows"][0]["churned_accounts"] == 2


@pytest.mark.asyncio
async def test_list_custom_reports_uses_today_fallback():
    repo = ReportRepository()
    repo.list_custom_reports = AsyncMock(
        return_value=[Row(id="r1", name="Q3", filters=None, metrics_included="a,b", created_at=None)]
    )
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_custom_reports(db, org_id="org-1")

    assert result[0]["filters"] == "All Accounts"
    assert result[0]["metrics_included"] == ["a", "b"]
    assert result[0]["created_at"] == today_str()


@pytest.mark.asyncio
async def test_create_custom_report_validates_and_commits():
    repo = ReportRepository()
    repo.create_custom_report = AsyncMock(return_value=Row(id="r1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-target")

    result = await service.create_custom_report(db, "My Report", "filter_x", current_user=user)

    assert repo.create_custom_report.await_args is not None
    data = repo.create_custom_report.await_args.kwargs["data"]
    assert data["organization_id"] == "org-target"
    assert data["name"] == "My Report"
    assert data["filters"] == "filter_x"
    assert result["status"] == "success"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_custom_report_empty_name_raises():
    repo = ReportRepository()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.create_custom_report(db, "   ", org_id="org-1")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_run_custom_report_found():
    repo = ReportRepository()
    repo.get_custom_report = AsyncMock(return_value=Row(id="r1", name="Enterprise Deals"))
    repo.total_won_revenue = AsyncMock(return_value=50000.0)
    repo.count_deals = AsyncMock(return_value=12)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.run_custom_report(db, "r1", org_id="org-1")

    assert result["report_type"] == "Enterprise Deals"
    assert result["metrics"]["total_revenue"] == 50000.0
    assert result["metrics"]["deals_analyzed"] == 12


@pytest.mark.asyncio
async def test_run_custom_report_not_found_raises_404():
    repo = ReportRepository()
    repo.get_custom_report = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.run_custom_report(db, "missing", org_id="org-1")


@pytest.mark.asyncio
async def test_delete_custom_report_not_found_raises_404():
    repo = ReportRepository()
    repo.get_custom_report = AsyncMock(return_value=None)
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.delete_custom_report(db, "missing", org_id="org-1")


@pytest.mark.asyncio
async def test_delete_custom_report_success():
    repo = ReportRepository()
    mock_report = Row(id="r1", name="Report 1")
    repo.get_custom_report = AsyncMock(return_value=mock_report)
    repo.delete_custom_report = AsyncMock()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_custom_report(db, "r1", org_id="org-1")

    repo.delete_custom_report.assert_awaited_once_with(db, mock_report)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_schedule_report_email_validations():
    repo = ReportRepository()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    # Invalid email
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(db, "sales-performance", "not-an-email", "Weekly", org_id="org-1")
    assert exc.value.status_code == 422

    # Invalid frequency
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(db, "sales-performance", "valid@email.com", "Yearly", org_id="org-1")
    assert exc.value.status_code == 422

    # Invalid report type
    with pytest.raises(APIException) as exc:
        await service.schedule_report_email(db, "invalid-type", "valid@email.com", "Weekly", org_id="org-1")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_schedule_report_email_sets_next_run():
    repo = ReportRepository()
    repo.create_scheduled_report = AsyncMock(return_value=Row(id="s1"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-custom")

    result = await service.schedule_report_email(
        db, "sales-performance", "lead@company.com", "Daily", current_user=user
    )

    assert repo.create_scheduled_report.await_args is not None
    data = repo.create_scheduled_report.await_args.kwargs["data"]
    assert data["organization_id"] == "org-custom"
    assert data["email"] == "lead@company.com"
    assert data["frequency"] == "Daily"
    assert data["next_run"] is not None
    assert result["message"].startswith("Scheduled Daily")


@pytest.mark.asyncio
async def test_delete_scheduled_report():
    repo = ReportRepository()
    mock_sched = Row(id="s1")
    repo.get_scheduled_report = AsyncMock(return_value=mock_sched)
    repo.delete_scheduled_report = AsyncMock()
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_scheduled_report(db, "s1", org_id="org-1")

    repo.delete_scheduled_report.assert_awaited_once_with(db, mock_sched)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_export_report_pdf_validates_type_and_user():
    repo = ReportRepository()
    repo.create_export = AsyncMock(return_value=Row(download_url="https://api.crm.com/exports/analytics_sales-performance.pdf"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(org_id="org-sales", user_id="usr-alex")

    result = await service.export_report_pdf(db, "sales-performance", current_user=user)

    assert repo.create_export.await_args is not None
    data = repo.create_export.await_args.kwargs["data"]
    assert data["organization_id"] == "org-sales"
    assert data["requested_by"] == "usr-alex"
    assert data["file_format"] == "pdf"
    assert "pdf_url" in result


def test_today_str_format():
    value = today_str()
    assert len(value) == 10
    assert "-" in value


def test_compute_next_run_daily_and_weekly():
    base = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    daily = compute_next_run("Daily", base)
    assert daily == datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    weekly = compute_next_run("Weekly", base)
    assert weekly == datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc)


def test_compute_next_run_monthly_calendar_arithmetic():
    # Jan 31 -> Feb 28 (clamps to last day of Feb)
    jan31 = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    feb_run = compute_next_run("Monthly", jan31)
    assert feb_run.year == 2026
    assert feb_run.month == 2
    assert feb_run.day == 28

    # Dec 15 -> Jan 15 of next year
    dec15 = datetime(2026, 12, 15, 10, 0, tzinfo=timezone.utc)
    jan_run = compute_next_run("Monthly", dec15)
    assert jan_run.year == 2027
    assert jan_run.month == 1
    assert jan_run.day == 15


@pytest.mark.asyncio
async def test_export_report_pdf_raises_on_commit_failure():
    repo = ReportRepository()
    repo.create_export = AsyncMock(return_value=Row(download_url="https://api.crm.com/exports/test.pdf"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("DB connection lost")
    user = _make_user(org_id="org-fail", user_id="usr-1")

    with pytest.raises(APIException) as exc_info:
        await service.export_report_pdf(db, "sales-performance", current_user=user)
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_export_report_csv_resolves_org_user_fallback():
    repo = ReportRepository()
    repo.resolve_org_user_id = AsyncMock(return_value="usr-org-owner")
    repo.deals_for_csv = AsyncMock(return_value=[("Deal 1", 5000.0, "Closed Won")])
    repo.create_export = AsyncMock(return_value=Row(download_url="https://api.crm.com/exports/csv.csv"))
    service = ReportService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.export_report_csv(db, "sales-performance", org_id="org-fallback")

    repo.resolve_org_user_id.assert_awaited_once_with(db, "org-fallback")
    assert repo.create_export.await_args is not None
    assert repo.create_export.await_args.kwargs["data"]["requested_by"] == "usr-org-owner"
    assert "csv_url" in result