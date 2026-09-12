from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.order import OrderResponse, OrderStatus, OrderStatusUpdate
from app.services.order_service import order_service

router = APIRouter()


@router.get(
    "",
    response_model=list[OrderResponse],
    dependencies=[Depends(require_permission("orders:read"))],
)
async def list_orders(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: OrderStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = {"status": status_filter, "search": search}
    items = await order_service.list(db, current_user, page=page, limit=limit, **filters)
    response.headers["X-Total-Count"] = str(await order_service.count(db, current_user, **filters))
    return items


@router.post(
    "/from-quote/{quote_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("orders:create"))],
)
async def create_order_from_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await order_service.create_from_quote(db, current_user, quote_id)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await order_service.get(db, current_user, order_id)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:update"))],
)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await order_service.update_status(db, current_user, order_id, payload.status)
