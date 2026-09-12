from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import MessageResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectStakeholderCreate,
    ProjectStakeholderResponse,
    ProjectUpdate,
)
from app.services.project_service import project_service

router = APIRouter()


@router.get(
    "",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_permission("projects:read"))],
)
async def list_projects(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = await project_service.list_projects(
        db, current_user, page=page, limit=limit, status=status, priority=priority, search=search
    )
    total = await project_service.count_projects(
        db, current_user, status=status, priority=priority, search=search
    )
    response.headers["X-Total-Count"] = str(total)
    return projects


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


@router.get(
    "/{project_id}/stakeholders",
    response_model=list[ProjectStakeholderResponse],
    dependencies=[
        Depends(require_permission("projects:read")),
        Depends(require_permission("contacts:read")),
    ],
)
async def list_stakeholders(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.list_stakeholders(db, current_user, project_id)


@router.post(
    "/{project_id}/stakeholders",
    response_model=ProjectStakeholderResponse,
    status_code=201,
    dependencies=[
        Depends(require_permission("projects:update")),
        Depends(require_permission("contacts:read")),
    ],
)
async def add_stakeholder(
    project_id: str,
    payload: ProjectStakeholderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await project_service.add_stakeholder(
        db, current_user, project_id, payload.contact_id, payload.role
    )


@router.delete(
    "/{project_id}/stakeholders/{stakeholder_id}",
    status_code=204,
    dependencies=[Depends(require_permission("projects:update"))],
)
async def remove_stakeholder(
    project_id: str,
    stakeholder_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await project_service.remove_stakeholder(db, current_user, project_id, stakeholder_id)
    return Response(status_code=204)
