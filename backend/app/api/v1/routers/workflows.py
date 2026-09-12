from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunResponse,
    WorkflowUpdate,
)
from app.services.workflow_service import workflow_service

router = APIRouter()


@router.get(
    "",
    response_model=list[WorkflowResponse],
    dependencies=[Depends(require_permission("workflows:read"))],
)
async def list_workflows(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await workflow_service.list(db, user, page, limit)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("workflows:create"))],
)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await workflow_service.create(db, user, payload)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    dependencies=[Depends(require_permission("workflows:read"))],
)
async def get_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await workflow_service.get(db, user, workflow_id)


@router.patch(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    dependencies=[Depends(require_permission("workflows:update"))],
)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await workflow_service.update(db, user, workflow_id, payload)


@router.delete(
    "/{workflow_id}",
    status_code=204,
    dependencies=[Depends(require_permission("workflows:delete"))],
)
async def delete_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await workflow_service.delete(db, user, workflow_id)
    return Response(status_code=204)


@router.get(
    "/{workflow_id}/runs",
    response_model=list[WorkflowRunResponse],
    dependencies=[Depends(require_permission("workflows:read"))],
)
async def workflow_runs(
    workflow_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await workflow_service.runs(db, user, workflow_id)
