from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.schemas.crm_schemas import DashboardKPIs, MessageResponse
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get("/kpis", response_model=DashboardKPIs, summary="Get main dashboard executive KPIs", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_kpis(db)


@router.get("/sales-funnel", summary="Get sales stage conversion funnel data", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_sales_funnel(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_sales_funnel(db)


@router.get("/revenue-chart", summary="Get monthly revenue vs target comparison", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_revenue_chart(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_revenue_chart(db)


@router.get("/top-performers", summary="Get top sales rep leaderboard", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_top_performers(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_top_performers(db)


@router.get("/lead-conversions", summary="Get lead source conversion distribution", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_lead_conversions(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_lead_conversions(db)


@router.get("/activities-summary", summary="Get daily sales activities summary", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_activities_summary(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_activities_summary(db)


@router.get("/recent-deals", summary="Get recent deal updates stream", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_recent_deals(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_recent_deals(db)


@router.get("/ai-insights", summary="Get AI-generated pipeline executive summary", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_dashboard_ai_insights(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_ai_insights(db)


@router.get("/custom-widgets", summary="Get user customized dashboard widgets layout", dependencies=[Depends(require_permission("dashboard:read"))])
async def get_custom_widgets(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.get_custom_widgets(db)


@router.post("/custom-widgets", response_model=MessageResponse, summary="Save user dashboard widget preferences", dependencies=[Depends(require_permission("dashboard:customize"))])
async def save_custom_widgets(widgets: List[Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    return await dashboard_service.save_custom_widgets(db, widgets)