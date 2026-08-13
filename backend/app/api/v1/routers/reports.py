from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.crm_schemas import MessageResponse, ReportData
from app.services.report_service import report_service

router = APIRouter()


@router.get("/sales-performance", response_model=ReportData, summary="Get overall sales rep revenue performance report")
async def get_sales_performance_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_sales_performance_report(db)


@router.get("/pipeline-velocity", response_model=ReportData, summary="Get average days spent in each deal stage")
async def get_pipeline_velocity_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_pipeline_velocity_report(db)


@router.get("/win-loss-ratio", response_model=ReportData, summary="Get win vs loss ratio breakdown report")
async def get_win_loss_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_win_loss_report(db)


@router.get("/lead-attribution", response_model=ReportData, summary="Get lead source ROI & multi-touch attribution model")
async def get_lead_attribution_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_lead_attribution_report(db)


@router.get("/rep-leaderboard", response_model=ReportData, summary="Get rep conversion ranking leaderboard")
async def get_rep_leaderboard_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_rep_leaderboard_report(db)


@router.get("/revenue-forecasting", response_model=ReportData, summary="Get predictive revenue forecast report")
async def get_revenue_forecasting_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_revenue_forecasting_report(db)


@router.get("/activity-metrics", response_model=ReportData, summary="Get call, email, and meeting activity output per rep")
async def get_activity_metrics_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_activity_metrics_report(db)


@router.get("/deal-duration", response_model=ReportData, summary="Get average sales cycle length analysis")
async def get_deal_duration_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_deal_duration_report(db)


@router.get("/customer-acquisition-cost", response_model=ReportData, summary="Get CAC report")
async def get_cac_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_cac_report(db)


@router.get("/customer-lifetime-value", response_model=ReportData, summary="Get LTV report")
async def get_ltv_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_ltv_report(db)


@router.get("/churn-analysis", response_model=ReportData, summary="Get customer churn rate & lost ARR analytics")
async def get_churn_analysis_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_churn_analysis_report(db)


@router.get("/quota-attainment", response_model=ReportData, summary="Get rep quota completion progress")
async def get_quota_attainment_report(db: AsyncSession = Depends(get_db)):
    return await report_service.get_quota_attainment_report(db)


@router.get("/custom-reports", summary="List saved custom report queries")
async def list_custom_reports(db: AsyncSession = Depends(get_db)):
    return await report_service.list_custom_reports(db)


@router.post("/custom-reports", response_model=MessageResponse, summary="Create new custom report query builder entry")
async def create_custom_report(
    name: str = Query(...),
    filters: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.create_custom_report(db, name, filters)


@router.get("/custom-reports/{report_id}", response_model=ReportData, summary="Execute custom report query and fetch results")
async def run_custom_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return await report_service.run_custom_report(db, report_id)


@router.delete("/custom-reports/{report_id}", response_model=MessageResponse, summary="Delete custom report entry")
async def delete_custom_report(report_id: str, db: AsyncSession = Depends(get_db)):
    return await report_service.delete_custom_report(db, report_id)


@router.post("/export/pdf", summary="Export report view to PDF document")
async def export_report_pdf(report_type: str = Query("sales-performance"), db: AsyncSession = Depends(get_db)):
    return await report_service.export_report_pdf(db, report_type)


@router.post("/export/csv", summary="Generate CSV report dataset and upload to MinIO S3 bucket")
async def export_report_csv(report_type: str = Query("sales-performance"), db: AsyncSession = Depends(get_db)):
    return await report_service.export_report_csv(db, report_type)


@router.post("/schedule", response_model=MessageResponse, summary="Schedule recurring automated email delivery of report")
async def schedule_report_email(
    report_type: str = Query(...),
    email: str = Query(...),
    frequency: str = Query("Weekly"),
    db: AsyncSession = Depends(get_db),
):
    return await report_service.schedule_report_email(db, report_type, email, frequency)


@router.get("/scheduled", summary="List active scheduled automated report jobs")
async def list_scheduled_reports(db: AsyncSession = Depends(get_db)):
    return await report_service.list_scheduled_reports(db)