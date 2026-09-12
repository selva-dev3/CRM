from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_valid_org_id, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.activity import ActivityResponse
from app.services.activity_service import activity_service

router = APIRouter()


@router.get(
    "",
    response_model=list[ActivityResponse],
    dependencies=[Depends(require_permission("activities:read"))],
)
async def list_activities(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    module: Literal[
        "leads",
        "deals",
        "tasks",
        "meetings",
        "calls",
        "emails",
        "notes",
        "calendar",
        "whatsapp",
    ]
    | None = Query(None),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await get_valid_org_id(db, current_user)
    items, total = await activity_service.list_activities(
        db,
        current_user,
        organization_id=organization_id,
        page=page,
        limit=limit,
        module=module,
        search=search,
    )
    response.headers["X-Total-Count"] = str(total)
    return items
