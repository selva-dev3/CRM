from fastapi import APIRouter
from app.schemas.crm_schemas import DashboardKPIs

router = APIRouter()

@router.get("/kpis", response_model=DashboardKPIs, summary="Get real-time dashboard KPIs")
async def get_dashboard_kpis():
    """Retrieves executive summary metrics, sales win rate, and recent activities."""
    return {
        "total_leads": 1248,
        "deals_won_amount": 452000.0,
        "win_rate_percentage": 64.2,
        "ai_lead_score_avg": 88.5,
        "recent_activity": [
            {"action": "Deal Closed", "detail": "Acme License ($45,000)", "timestamp": "10 mins ago"},
            {"action": "New Lead Scored", "detail": "TechCorp (Score: 92)", "timestamp": "25 mins ago"}
        ]
    }
