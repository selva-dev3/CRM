from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.crm_schemas import MessageResponse, ReportData
from app.schemas.report_schemas import (
    CsvExportResponse,
    CustomReportCreate,
    CustomReportItem,
    ExportReportRequest,
    PdfExportResponse,
    ScheduleReportCreate,
    ScheduledReportItem,
)
from app.services.report_service import report_service

router = APIRouter()


@router.get(
    "/sales-performance",
    response_model=ReportData,
    summary="Get overall sales rep revenue performance report",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_sales_performance_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_sales_performance_report(db, current_user=current_user)


@router.get(
    "/pipeline-velocity",
    response_model=ReportData,
    summary="Get average days spent in each deal stage",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_pipeline_velocity_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_pipeline_velocity_report(db, current_user=current_user)


@router.get(
    "/win-loss-ratio",
    response_model=ReportData,
    summary="Get win vs loss ratio breakdown report",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_win_loss_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_win_loss_report(db, current_user=current_user)


@router.get(
    "/lead-attribution",
    response_model=ReportData,
    summary="Get lead source ROI & multi-touch attribution model",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_lead_attribution_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_lead_attribution_report(db, current_user=current_user)


@router.get(
    "/rep-leaderboard",
    response_model=ReportData,
    summary="Get rep conversion ranking leaderboard",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_rep_leaderboard_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_rep_leaderboard_report(db, current_user=current_user)


@router.get(
    "/revenue-forecasting",
    response_model=ReportData,
    summary="Get predictive revenue forecast report",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_revenue_forecasting_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_revenue_forecasting_report(db, current_user=current_user)


@router.get(
    "/activity-metrics",
    response_model=ReportData,
    summary="Get call, email, and meeting activity output per rep",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_activity_metrics_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_activity_metrics_report(db, current_user=current_user)


@router.get(
    "/deal-duration",
    response_model=ReportData,
    summary="Get average sales cycle length analysis",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_deal_duration_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_deal_duration_report(db, current_user=current_user)


@router.get(
    "/customer-acquisition-cost",
    response_model=ReportData,
    summary="Get CAC report",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_cac_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_cac_report(db, current_user=current_user)


@router.get(
    "/customer-lifetime-value",
    response_model=ReportData,
    summary="Get LTV report",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_ltv_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_ltv_report(db, current_user=current_user)


@router.get(
    "/churn-analysis",
    response_model=ReportData,
    summary="Get customer churn rate & lost ARR analytics",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_churn_analysis_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_churn_analysis_report(db, current_user=current_user)


@router.get(
    "/quota-attainment",
    response_model=ReportData,
    summary="Get rep quota completion progress",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_quota_attainment_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_quota_attainment_report(db, current_user=current_user)


@router.get(
    "/custom-reports",
    response_model=List[CustomReportItem],
    summary="List saved custom report queries",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_custom_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.list_custom_reports(db, current_user=current_user, limit=limit, offset=offset)


@router.post(
    "/custom-reports",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new custom report query builder entry",
    dependencies=[Depends(require_permission("reports:create"))],
)
async def create_custom_report(
    payload: CustomReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.create_custom_report(
        db, name=payload.name, filters=payload.filters, current_user=current_user
    )


@router.get(
    "/custom-reports/{report_id}",
    response_model=ReportData,
    summary="Execute custom report query and fetch results",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def run_custom_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.run_custom_report(db, report_id=report_id, current_user=current_user)


@router.delete(
    "/custom-reports/{report_id}",
    response_model=MessageResponse,
    summary="Delete custom report entry",
    dependencies=[Depends(require_permission("reports:create"))],
)
async def delete_custom_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.delete_custom_report(
        db, report_id=report_id, current_user=current_user
    )


@router.post(
    "/export/pdf",
    response_model=PdfExportResponse,
    summary="Export report view to PDF document",
    dependencies=[Depends(require_permission("reports:export"))],
)
async def export_report_pdf(
    payload: ExportReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.export_report_pdf(
        db, report_type=payload.report_type, current_user=current_user
    )


@router.post(
    "/export/csv",
    response_model=CsvExportResponse,
    summary="Generate CSV report dataset and upload to MinIO S3 bucket",
    dependencies=[Depends(require_permission("reports:export"))],
)
async def export_report_csv(
    payload: ExportReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.export_report_csv(
        db, report_type=payload.report_type, current_user=current_user
    )


@router.post(
    "/schedule",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule recurring automated email delivery of report",
    dependencies=[Depends(require_permission("reports:schedule"))],
)
async def schedule_report_email(
    payload: ScheduleReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.schedule_report_email(
        db,
        report_type=payload.report_type,
        email=str(payload.email),
        frequency=payload.frequency.value if hasattr(payload.frequency, "value") else str(payload.frequency),
        current_user=current_user,
    )


@router.get(
    "/scheduled",
    response_model=List[ScheduledReportItem],
    summary="List active scheduled automated report jobs",
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_scheduled_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.list_scheduled_reports(db, current_user=current_user, limit=limit, offset=offset)


@router.delete(
    "/scheduled/{schedule_id}",
    response_model=MessageResponse,
    summary="Cancel / delete scheduled automated report job",
    dependencies=[Depends(require_permission("reports:schedule"))],
)
async def delete_scheduled_report(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.delete_scheduled_report(
        db, schedule_id=schedule_id, current_user=current_user
    )