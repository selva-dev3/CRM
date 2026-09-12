from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import MessageResponse
from app.schemas.milestone import MilestoneCreate, MilestoneResponse, MilestoneUpdate
from app.services.milestone_service import milestone_service

router = APIRouter()


@router.get(
    "",
    response_model=list[MilestoneResponse],
    dependencies=[Depends(require_permission("projects:read"))],
)
async def list_milestones(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    project_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {"project_id": project_id, "status": status_filter}
    items = await milestone_service.list(db, current_user, page=page, limit=limit, **filters)
    response.headers["X-Total-Count"] = str(
        await milestone_service.count(db, current_user, **filters)
    )
    return items


@router.post(
    "",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("projects:create"))],
)
async def create_milestone(
    payload: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await milestone_service.create(db, current_user, payload)


@router.put(
    "/{milestone_id}",
    response_model=MilestoneResponse,
    dependencies=[Depends(require_permission("projects:update"))],
)
async def update_milestone(
    milestone_id: str,
    payload: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await milestone_service.update(db, current_user, milestone_id, payload)


@router.delete(
    "/{milestone_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission("projects:delete"))],
)
async def delete_milestone(
    milestone_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await milestone_service.delete(db, current_user, milestone_id)
