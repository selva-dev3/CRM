from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException, ForbiddenError
from app.core.permissions import effective_organization_id
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
)
from app.services.dashboard_service import dashboard_service

router = APIRouter()


def _organization_id(user: User) -> str:
    organization_id = effective_organization_id(user)
    if not organization_id:
        raise ForbiddenError(message="Authenticated organization context is required")
    return organization_id


def _validate_date_range(start_at: datetime | None, end_at: datetime | None) -> None:
    if (start_at is None) != (end_at is None):
        raise APIException(
            status_code=422,
            code="INVALID_DATE_RANGE",
            message="start_at and end_at must be provided together",
        )
    if start_at and end_at and start_at >= end_at:
        raise APIException(
            status_code=422,
            code="INVALID_DATE_RANGE",
            message="start_at must be earlier than end_at",
        )


@router.get(
    "/kpis",
    response_model=DashboardKPIs,
    summary="Get main dashboard executive KPIs",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_dashboard_kpis(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_kpis(
        db,
        _organization_id(current_user),
        start_at=start_at,
        end_at=end_at,
        current_user=current_user,
    )


@router.get(
    "/sales-funnel",
    response_model=list[FunnelStageResponse],
    summary="Get sales stage conversion funnel data",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_sales_funnel(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_sales_funnel(
        db, _organization_id(current_user), current_user
    )


@router.get(
    "/revenue-chart",
    response_model=RevenueChartResponse,
    summary="Get monthly closed-won revenue",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_revenue_chart(
    start_at: datetime = Query(...),
    end_at: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_revenue_chart(
        db,
        _organization_id(current_user),
        start_at=start_at,
        end_at=end_at,
        current_user=current_user,
    )


@router.get(
    "/top-performers",
    response_model=list[TopPerformerResponse],
    summary="Get top sales rep leaderboard",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_top_performers(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_top_performers(
        db, _organization_id(current_user), current_user, start_at=start_at, end_at=end_at
    )


@router.get(
    "/lead-conversions",
    response_model=list[LeadConversionResponse],
    summary="Get lead source conversion distribution",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_lead_conversions(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_lead_conversions(
        db, _organization_id(current_user), current_user, start_at=start_at, end_at=end_at
    )


@router.get(
    "/activities-summary",
    response_model=ActivitiesSummaryResponse,
    summary="Get daily sales activities summary",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_activities_summary(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_activities_summary(
        db, _organization_id(current_user), current_user, start_at=start_at, end_at=end_at
    )


@router.get(
    "/recent-deals",
    response_model=list[RecentDealResponse],
    summary="Get recent deal updates stream",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_recent_deals(
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_date_range(start_at, end_at)
    return await dashboard_service.get_recent_deals(
        db, _organization_id(current_user), current_user, start_at=start_at, end_at=end_at
    )


@router.get(
    "/ai-insights",
    response_model=DashboardAiInsightsResponse,
    summary="Get AI-generated pipeline executive summary",
    dependencies=[
        Depends(require_permission("dashboard:read")),
        Depends(require_permission("ai:generate")),
        Depends(require_permission("deals:read")),
    ],
)
async def get_dashboard_ai_insights(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_ai_insights(db, _organization_id(current_user), current_user)


@router.get(
    "/custom-widgets",
    response_model=list[CustomWidgetResponse],
    summary="Get user customized dashboard widgets layout",
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_custom_widgets(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await dashboard_service.get_custom_widgets(
        db, _organization_id(current_user), current_user.id
    )


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
        _organization_id(current_user),
        [widget.model_dump() for widget in widgets],
        current_user.id,
    )
