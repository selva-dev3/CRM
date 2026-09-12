from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.team import (
    TeamCreate,
    TeamDetailResponse,
    TeamMemberUpdate,
    TeamResponse,
    TeamUpdate,
)
from app.services.team_service import team_service

router = APIRouter()


@router.get(
    "", response_model=list[TeamResponse], dependencies=[Depends(require_permission("teams:read"))]
)
async def list_teams(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await team_service.list(db, user, search, page, limit)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("teams:create"))],
)
async def create_team(
    payload: TeamCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await team_service.create(db, user, payload)


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    dependencies=[Depends(require_permission("teams:read"))],
)
async def get_team(
    team_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await team_service.detail(db, user, team_id)


@router.patch(
    "/{team_id}",
    response_model=TeamResponse,
    dependencies=[Depends(require_permission("teams:update"))],
)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await team_service.update(db, user, team_id, payload)


@router.delete(
    "/{team_id}", status_code=204, dependencies=[Depends(require_permission("teams:delete"))]
)
async def delete_team(
    team_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await team_service.delete(db, user, team_id)
    return Response(status_code=204)


@router.put(
    "/{team_id}/members",
    response_model=TeamDetailResponse,
    dependencies=[Depends(require_permission("teams:manage_members"))],
)
async def add_member(
    team_id: str,
    payload: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await team_service.add_member(db, user, team_id, payload)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permission("teams:manage_members"))],
)
async def remove_member(
    team_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await team_service.remove_member(db, user, team_id, user_id)
    return Response(status_code=204)
