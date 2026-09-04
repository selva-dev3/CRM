from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import MessageResponse
from app.schemas.dashboard import (
    ActivitiesSummaryResponse,
    CustomWidgetResponse,
    CustomWidgetSaveRequest,
    DashboardAiInsightsResponse,
    DashboardKPIs,
    FunnelStageResponse,
    LeadConversionResponse,
    RecentDealResponse,
    RevenueChartResponse,
    TopPerformerResponse,
    UnavailableMetricResponse,
)
from app.services.dashboard_service import dashboard_service

router = APIRouter()


@router.get(
    "/kpis",
    response_model=DashboardKPIs,
    summary="Get main dashboard executive KPIs",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_dashboard_kpis(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_kpis(db, current_user.organization_id)


@router.get(
    "/sales-funnel",
    response_model=list[FunnelStageResponse],
    summary="Get sales stage conversion funnel data",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_sales_funnel(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_sales_funnel(db, current_user.organization_id)


@router.get(
    "/revenue-chart",
    response_model=RevenueChartResponse,
    responses={
        501: {
            "model": UnavailableMetricResponse,
            "description": "Required source data is not recorded",
        }
    },
    summary="Get monthly revenue vs target comparison",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_revenue_chart(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_revenue_chart(db, current_user.organization_id)


@router.get(
    "/top-performers",
    response_model=list[TopPerformerResponse],
    summary="Get top sales rep leaderboard",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_top_performers(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_top_performers(db, current_user.organization_id)


@router.get(
    "/lead-conversions",
    response_model=list[LeadConversionResponse],
    summary="Get lead source conversion distribution",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_lead_conversions(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_lead_conversions(db, current_user.organization_id)


@router.get(
    "/activities-summary",
    response_model=ActivitiesSummaryResponse,
    summary="Get daily sales activities summary",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_activities_summary(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_activities_summary(db, current_user.organization_id)


@router.get(
    "/recent-deals",
    response_model=list[RecentDealResponse],
    summary="Get recent deal updates stream",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_recent_deals(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_recent_deals(db, current_user.organization_id)


@router.get(
    "/ai-insights",
    response_model=DashboardAiInsightsResponse,
    summary="Get AI-generated pipeline executive summary",
    dependencies=[
        Depends(require_permission("dashboard:read")),
        Depends(require_permission("ai:generate")),
    ],
)
async def get_dashboard_ai_insights(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_ai_insights(db, current_user)


@router.get(
    "/custom-widgets",
    response_model=list[CustomWidgetResponse],
    summary="Get user customized dashboard widgets layout",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_custom_widgets(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_custom_widgets(db, current_user.organization_id)


@router.post(
    "/custom-widgets",
    response_model=MessageResponse,
    summary="Save user dashboard widget preferences",
    dependencies=[Depends(require_permission("dashboard:customize"))],
)
async def save_custom_widgets(
    widgets: list[CustomWidgetSaveRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await dashboard_service.save_custom_widgets(
        db,
        current_user.organization_id,
        [widget.model_dump() for widget in widgets],
    )
