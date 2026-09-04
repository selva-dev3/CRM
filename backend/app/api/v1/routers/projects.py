from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import MessageResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import project_service

router = APIRouter()


@router.get(
    "",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_permission("projects:read"))],
)
async def list_projects(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.list_projects(
        db, current_user, page=page, limit=limit, status=status, priority=priority
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("projects:create"))],
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.create_project(db, current_user, payload)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_permission("projects:read"))],
)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.get_project(db, current_user, project_id)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_permission("projects:update"))],
)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.update_project(db, current_user, project_id, payload)


@router.delete(
    "/{project_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission("projects:delete"))],
)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.delete_project(db, current_user, project_id)
