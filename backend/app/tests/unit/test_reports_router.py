from unittest.mock import AsyncMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers.reports import (
    create_custom_report,
    delete_custom_report,
    delete_scheduled_report,
    export_report_csv,
    export_report_pdf,
    get_sales_performance_report,
    list_custom_reports,
    list_scheduled_reports,
    run_custom_report,
    schedule_report_email,
)
from app.core.errors import NotFoundError
from app.models.user import User
from app.schemas.report_schemas import (
    CustomReportCreate,
    ExportReportRequest,
    ReportFrequencyEnum,
    ScheduleReportCreate,
)
from app.services.report_service import report_service


def _make_user(org_id="org-test", user_id="user-1"):
    return User(
        id=user_id,
        email="test@crm.com",
        name="Test User",
        organization_id=org_id,
        role="Admin",
        hashed_password="hash",
    )


@pytest.mark.asyncio
async def test_get_sales_performance_router_passes_current_user(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_service_call = AsyncMock(return_value={
        "report_type": "Sales Performance",
        "metrics": {"total_revenue": 100.0, "monthly_target": 200.0, "table_rows": []},
        "generated_at": "2026-08-23",
    })
    monkeypatch.setattr(report_service, "get_sales_performance_report", mock_service_call)

    res = await get_sales_performance_report(current_user=user, db=db)

    assert res["report_type"] == "Sales Performance"
    mock_service_call.assert_awaited_once_with(db, current_user=user)


@pytest.mark.asyncio
async def test_create_custom_report_router_passes_user(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_create = AsyncMock(return_value={"message": "Custom report created", "status": "success"})
    monkeypatch.setattr(report_service, "create_custom_report", mock_create)

    res = await create_custom_report(name="High Value Deals", filters="amount > 10000", current_user=user, db=db)

    assert res["status"] == "success"
    mock_create.assert_awaited_once_with(
        db, name="High Value Deals", filters="amount > 10000", current_user=user
    )


@pytest.mark.asyncio
async def test_run_custom_report_router_raises_not_found(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_run = AsyncMock(side_effect=NotFoundError(message="Custom report not found"))
    monkeypatch.setattr(report_service, "run_custom_report", mock_run)

    with pytest.raises(NotFoundError):
        await run_custom_report(report_id="rep-unknown", current_user=user, db=db)


@pytest.mark.asyncio
async def test_delete_custom_report_router(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_del = AsyncMock(return_value={"message": "Deleted", "status": "success"})
    monkeypatch.setattr(report_service, "delete_custom_report", mock_del)

    res = await delete_custom_report(report_id="rep-1", current_user=user, db=db)
    assert res["status"] == "success"
    mock_del.assert_awaited_once_with(db, report_id="rep-1", current_user=user)


@pytest.mark.asyncio
async def test_schedule_report_email_router(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_sched = AsyncMock(return_value={"message": "Scheduled", "status": "success"})
    monkeypatch.setattr(report_service, "schedule_report_email", mock_sched)

    res = await schedule_report_email(
        report_type="sales-performance",
        email="alex@acme.com",
        frequency="Weekly",
        current_user=user,
        db=db,
    )
    assert res["status"] == "success"
    mock_sched.assert_awaited_once_with(
        db,
        report_type="sales-performance",
        email="alex@acme.com",
        frequency="Weekly",
        current_user=user,
    )


@pytest.mark.asyncio
async def test_delete_scheduled_report_router(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_del = AsyncMock(return_value={"message": "Scheduled report deleted", "status": "success"})
    monkeypatch.setattr(report_service, "delete_scheduled_report", mock_del)

    res = await delete_scheduled_report(schedule_id="sched-1", current_user=user, db=db)
    assert res["status"] == "success"
    mock_del.assert_awaited_once_with(db, schedule_id="sched-1", current_user=user)


@pytest.mark.asyncio
async def test_export_pdf_and_csv_router(monkeypatch):
    user = _make_user(org_id="org-99", user_id="user-alex")
    db = AsyncMock(spec=AsyncSession)
    mock_pdf = AsyncMock(return_value={"pdf_url": "https://api.crm.com/exports/analytics.pdf"})
    mock_csv = AsyncMock(return_value={"csv_url": "https://api.crm.com/exports/analytics.csv"})
    monkeypatch.setattr(report_service, "export_report_pdf", mock_pdf)
    monkeypatch.setattr(report_service, "export_report_csv", mock_csv)

    res_pdf = await export_report_pdf(report_type="sales-performance", current_user=user, db=db)
    res_csv = await export_report_csv(report_type="sales-performance", current_user=user, db=db)

    assert "pdf_url" in res_pdf
    assert "csv_url" in res_csv
    mock_pdf.assert_awaited_once_with(db, report_type="sales-performance", current_user=user)
    mock_csv.assert_awaited_once_with(db, report_type="sales-performance", current_user=user)


@pytest.mark.asyncio
async def test_schedule_report_email_router_with_body_payload(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_sched = AsyncMock(return_value={"message": "Scheduled", "status": "success"})
    monkeypatch.setattr(report_service, "schedule_report_email", mock_sched)

    payload = ScheduleReportCreate(
        report_type="pipeline-velocity",
        email="alex@company.com",
        frequency=ReportFrequencyEnum.MONTHLY,
    )

    res = await schedule_report_email(payload=payload, current_user=user, db=db)
    assert res["status"] == "success"
    mock_sched.assert_awaited_once_with(
        db,
        report_type="pipeline-velocity",
        email="alex@company.com",
        frequency="Monthly",
        current_user=user,
    )


@pytest.mark.asyncio
async def test_create_custom_report_router_with_body_payload(monkeypatch):
    user = _make_user(org_id="org-99")
    db = AsyncMock(spec=AsyncSession)
    mock_create = AsyncMock(return_value={"message": "Created", "status": "success"})
    monkeypatch.setattr(report_service, "create_custom_report", mock_create)

    payload = CustomReportCreate(name="Q4 Revenue", filters="stage == 'Closed Won'")

    res = await create_custom_report(payload=payload, current_user=user, db=db)
    assert res["status"] == "success"
    mock_create.assert_awaited_once_with(
        db, name="Q4 Revenue", filters="stage == 'Closed Won'", current_user=user
    )
