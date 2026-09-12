from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard_layout import (
    DashboardLayoutCreate,
    DashboardLayoutResponse,
    DashboardLayoutUpdate,
)
from app.services.dashboard_layout_service import dashboard_layout_service

router = APIRouter()


@router.get(
    "",
    response_model=list[DashboardLayoutResponse],
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def list_dashboards(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await dashboard_layout_service.list(db, user, page, limit)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.post(
    "",
    response_model=DashboardLayoutResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("dashboard:customize"))],
)
async def create_dashboard(
    payload: DashboardLayoutCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await dashboard_layout_service.create(db, user, payload)


@router.get(
    "/{layout_id}",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def get_dashboard(
    layout_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await dashboard_layout_service.get(db, user, layout_id)


@router.patch(
    "/{layout_id}",
    response_model=DashboardLayoutResponse,
    dependencies=[Depends(require_permission("dashboard:customize"))],
)
async def update_dashboard(
    layout_id: str,
    payload: DashboardLayoutUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await dashboard_layout_service.update(db, user, layout_id, payload)


@router.delete(
    "/{layout_id}",
    status_code=204,
    dependencies=[Depends(require_permission("dashboard:customize"))],
)
async def delete_dashboard(
    layout_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await dashboard_layout_service.delete(db, user, layout_id)
    return Response(status_code=204)
