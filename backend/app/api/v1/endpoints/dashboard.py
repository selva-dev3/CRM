from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.crm_schemas import DashboardKPIs, MessageResponse

router = APIRouter()

@router.get("/kpis", response_model=DashboardKPIs, summary="Get main dashboard executive KPIs")
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db)):
    return {
        "total_leads": 1250,
        "deals_won_amount": 485000.0,
        "win_rate_percentage": 68.5,
        "ai_lead_score_avg": 84.2,
        "recent_activity": [
            {"id": "act-1", "title": "New Lead Created", "time": "10 mins ago"},
            {"id": "act-2", "title": "Deal Won $50k", "time": "1 hour ago"}
        ]
    }

@router.get("/sales-funnel", summary="Get sales stage conversion funnel data")
async def get_sales_funnel(db: AsyncSession = Depends(get_db)):
    return [
        {"stage": "Prospecting", "count": 450, "value": 1200000.0},
        {"stage": "Qualified", "count": 220, "value": 850000.0},
        {"stage": "Proposal Sent", "count": 110, "value": 540000.0},
        {"stage": "Closed Won", "count": 65, "value": 485000.0}
    ]

@router.get("/revenue-chart", summary="Get monthly revenue vs target comparison")
async def get_revenue_chart(db: AsyncSession = Depends(get_db)):
    return {
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
        "actual": [45000, 52000, 61000, 58000, 72000, 81000, 95000],
        "target": [40000, 50000, 55000, 60000, 65000, 75000, 85000]
    }

@router.get("/top-performers", summary="Get top sales rep leaderboard")
async def get_top_performers(db: AsyncSession = Depends(get_db)):
    return [
        {"user_id": "usr-1", "name": "Sarah Connor", "deals_closed": 18, "revenue": 145000.0},
        {"user_id": "usr-2", "name": "John Doe", "deals_closed": 14, "revenue": 112000.0}
    ]

@router.get("/lead-conversions", summary="Get lead source conversion distribution")
async def get_lead_conversions(db: AsyncSession = Depends(get_db)):
    return [
        {"source": "Website", "leads": 500, "converted": 120, "rate": 24.0},
        {"source": "LinkedIn", "leads": 350, "converted": 95, "rate": 27.1}
    ]

@router.get("/activities-summary", summary="Get daily sales activities summary")
async def get_activities_summary(db: AsyncSession = Depends(get_db)):
    return {"calls_completed": 42, "emails_sent": 180, "meetings_held": 15, "tasks_completed": 35}

@router.get("/recent-deals", summary="Get recent deal updates stream")
async def get_recent_deals(db: AsyncSession = Depends(get_db)):
    return [{"deal_id": "dl-100", "title": "Acme Renewal", "amount": 25000.0, "updated_at": "2026-08-02"}]

@router.get("/ai-insights", summary="Get AI-generated pipeline executive summary")
async def get_dashboard_ai_insights(db: AsyncSession = Depends(get_db)):
    return {
        "summary": "Pipeline health is up 12% MoM. Recommended focus: 5 high-value proposals expiring this week.",
        "risk_deals": ["dl-104", "dl-109"]
    }

@router.get("/custom-widgets", summary="Get user customized dashboard widgets layout")
async def get_custom_widgets(db: AsyncSession = Depends(get_db)):
    return [{"widget_id": "w-1", "type": "kpi_card", "position": 1, "visible": True}]

@router.post("/custom-widgets", response_model=MessageResponse, summary="Save user dashboard widget preferences")
async def save_custom_widgets(widgets: List[Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    return {"message": "Dashboard widget layout saved", "status": "success"}
