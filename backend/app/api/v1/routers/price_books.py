from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import MessageResponse
from app.schemas.price_book import (
    PriceBookContextResponse,
    PriceBookCreate,
    PriceBookEntryResponse,
    PriceBookEntryUpsert,
    PriceBookResponse,
    PriceBookUpdate,
)
from app.services.price_book_service import price_book_service

router = APIRouter()


@router.get(
    "/context",
    response_model=PriceBookContextResponse,
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_price_book_context(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await price_book_service.context(db, current_user)


@router.get(
    "",
    response_model=list[PriceBookResponse],
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_price_books(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await price_book_service.list(db, current_user)


@router.post(
    "",
    response_model=PriceBookResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_price_book(
    payload: PriceBookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.create(db, current_user, payload)


@router.put(
    "/{price_book_id}",
    response_model=PriceBookResponse,
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_price_book(
    price_book_id: str,
    payload: PriceBookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.update(db, current_user, price_book_id, payload)


@router.delete(
    "/{price_book_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission("products:delete"))],
)
async def delete_price_book(
    price_book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.delete(db, current_user, price_book_id)


@router.get(
    "/{price_book_id}/entries",
    response_model=list[PriceBookEntryResponse],
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_price_book_entries(
    price_book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.entries(db, current_user, price_book_id)


@router.put(
    "/{price_book_id}/entries/{product_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission("products:update"))],
)
async def upsert_price_book_entry(
    price_book_id: str,
    product_id: str,
    payload: PriceBookEntryUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.upsert_entry(
        db, current_user, price_book_id, product_id, payload
    )


@router.delete(
    "/{price_book_id}/entries/{product_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission("products:update"))],
)
async def delete_price_book_entry(
    price_book_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await price_book_service.delete_entry(db, current_user, price_book_id, product_id)
