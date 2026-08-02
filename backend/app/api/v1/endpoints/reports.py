from fastapi import APIRouter
from app.schemas.crm_schemas import ReportData

router = APIRouter()

@router.get("/sales-forecast", response_model=ReportData, summary="Get AI Sales Forecast analytics report")
async def get_sales_forecast_report():
    return {
        "report_type": "AI Sales Forecast",
        "metrics": {"q3_projected_revenue": 1250000.0, "win_probability_avg": 72.4, "top_pipeline_stage": "Proposal"},
        "generated_at": "2026-08-02T12:00:00Z"
    }
