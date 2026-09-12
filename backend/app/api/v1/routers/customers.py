from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.support import CustomerResponse
from app.services.support_service import support_service

router = APIRouter()


@router.get(
    "",
    response_model=list[CustomerResponse],
    dependencies=[
        Depends(require_permission("contacts:read")),
        Depends(require_permission("companies:read")),
    ],
)
async def list_customers(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await support_service.list_customers(db, user, search, page, limit)
    response.headers["X-Total-Count"] = str(total)
    return rows
