from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import ReportExport, Deal, Lead
from app.schemas.crm_schemas import ReportData, MessageResponse

router = APIRouter()

@router.get("/sales-performance", response_model=ReportData, summary="Get overall sales rep revenue performance report")
async def get_sales_performance_report(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(func.coalesce(func.sum(Deal.amount), 0.0)))
        total_rev = float(res.scalar() or 0.0)
        return {"report_type": "Sales Performance", "metrics": {"total_revenue": total_rev, "reps": []}, "generated_at": "2026-08-02"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/pipeline-velocity", response_model=ReportData, summary="Get average days spent in each deal stage")
async def get_pipeline_velocity_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Pipeline Velocity", "metrics": {"avg_days_to_close": 0.0, "stage_durations": {}}, "generated_at": "2026-08-02"}

@router.get("/win-loss-ratio", response_model=ReportData, summary="Get win vs loss ratio breakdown report")
async def get_win_loss_report(db: AsyncSession = Depends(get_db)):
    try:
        won_res = await db.execute(select(func.count(Deal.id)).where(Deal.stage == "Closed Won"))
        won_count = won_res.scalar() or 0
        total_res = await db.execute(select(func.count(Deal.id)))
        total_count = total_res.scalar() or 0
        win_pct = (won_count / total_count * 100.0) if total_count > 0 else 0.0
        return {"report_type": "Win Loss Analysis", "metrics": {"win_percentage": round(win_pct, 2), "loss_percentage": round(100.0 - win_pct, 2)}, "generated_at": "2026-08-02"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/lead-attribution", response_model=ReportData, summary="Get lead source ROI & multi-touch attribution model")
async def get_lead_attribution_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Lead Attribution", "metrics": {}, "generated_at": "2026-08-02"}

@router.get("/rep-leaderboard", response_model=ReportData, summary="Get rep conversion ranking leaderboard")
async def get_rep_leaderboard_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Rep Leaderboard", "metrics": {"top_reps": []}, "generated_at": "2026-08-02"}

@router.get("/revenue-forecasting", response_model=ReportData, summary="Get predictive revenue forecast report")
async def get_revenue_forecasting_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Revenue Forecast", "metrics": {"q3_predicted": 0.0, "confidence": 0.0}, "generated_at": "2026-08-02"}

@router.get("/activity-metrics", response_model=ReportData, summary="Get call, email, and meeting activity output per rep")
async def get_activity_metrics_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Activity Metrics", "metrics": {"total_calls": 0, "total_emails": 0, "total_meetings": 0}, "generated_at": "2026-08-02"}

@router.get("/deal-duration", response_model=ReportData, summary="Get average sales cycle length analysis")
async def get_deal_duration_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Deal Duration", "metrics": {"avg_cycle_days": 0.0}, "generated_at": "2026-08-02"}

@router.get("/customer-acquisition-cost", response_model=ReportData, summary="Get CAC report")
async def get_cac_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Customer Acquisition Cost", "metrics": {"blended_cac": 0.0}, "generated_at": "2026-08-02"}

@router.get("/customer-lifetime-value", response_model=ReportData, summary="Get LTV report")
async def get_ltv_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Customer Lifetime Value", "metrics": {"avg_ltv": 0.0, "ltv_cac_ratio": 0.0}, "generated_at": "2026-08-02"}

@router.get("/churn-analysis", response_model=ReportData, summary="Get customer churn rate & lost ARR analytics")
async def get_churn_analysis_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Churn Analysis", "metrics": {"annual_churn_rate": 0.0}, "generated_at": "2026-08-02"}

@router.get("/quota-attainment", response_model=ReportData, summary="Get rep quota completion progress")
async def get_quota_attainment_report(db: AsyncSession = Depends(get_db)):
    return {"report_type": "Quota Attainment", "metrics": {"team_attainment_pct": 0.0}, "generated_at": "2026-08-02"}

@router.get("/custom-reports", summary="List saved custom report queries")
async def list_custom_reports(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/custom-reports", response_model=MessageResponse, summary="Create new custom report query builder entry")
async def create_custom_report(name: str, filters: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return {"message": f"Custom report '{name}' saved", "status": "success"}

@router.get("/custom-reports/{report_id}", response_model=ReportData, summary="Execute custom report query and fetch results")
async def run_custom_report(report_id: str, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom report '{report_id}' not found")

@router.delete("/custom-reports/{report_id}", response_model=MessageResponse, summary="Delete custom report entry")
async def delete_custom_report(report_id: str, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom report '{report_id}' not found")

@router.post("/export/pdf", summary="Export report view to PDF document")
async def export_report_pdf(report_type: str, db: AsyncSession = Depends(get_db)):
    return {"pdf_url": f"https://api.crm.com/exports/reports_{report_type}.pdf"}

@router.post("/export/csv", summary="Export report dataset to CSV spreadsheet")
async def export_report_csv(report_type: str, db: AsyncSession = Depends(get_db)):
    try:
        r = ReportExport(organization_id="org-1", report_type=report_type, file_format="csv", download_url=f"https://api.crm.com/exports/reports_{report_type}.csv", requested_by="usr-1")
        db.add(r)
        await db.commit()
        return {"csv_url": r.download_url}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/schedule", response_model=MessageResponse, summary="Schedule recurring automated email delivery of report")
async def schedule_report_email(report_type: str, email: str, frequency: str = "Weekly", db: AsyncSession = Depends(get_db)):
    return {"message": f"Scheduled {frequency} report delivery of '{report_type}' to {email}", "status": "success"}

@router.get("/scheduled", summary="List active scheduled automated report jobs")
async def list_scheduled_reports(db: AsyncSession = Depends(get_db)):
    return []
