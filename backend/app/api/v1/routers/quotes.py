from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    InvoiceResponse,
    MessageResponse,
    QuoteBase,
    QuoteResponse,
)
from app.services.quote_service import quote_service

router = APIRouter()


@router.post(
    "/{quote_id}/approve",
    response_model=QuoteResponse,
    dependencies=[Depends(require_permission("quotes:approve"))],
    deprecated=True,
)
async def approve_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.approve_quote(
        db, quote_id=quote_id, organization_id=organization_id, actor_id=current_user.id
    )


@router.get(
    "",
    summary="List quotes with pagination & filter",
    dependencies=[Depends(require_permission("quotes:read"))],
)
async def list_quotes(
    page: int = 1,
    limit: int = 20,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.list_quotes(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
    )


@router.post(
    "",
    response_model=QuoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new sales quote / proposal",
    dependencies=[Depends(require_permission("quotes:create"))],
)
async def create_quote(
    payload: QuoteBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await quote_service.create_quote(db, payload=payload, current_user=current_user)


@router.get(
    "/export/csv",
    summary="Export quotes list as CSV",
    dependencies=[Depends(require_permission("quotes:read"))],
)
async def export_quotes_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(message="Quote export is not implemented", status_code=501)


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import quotes from CSV file",
    dependencies=[Depends(require_permission("quotes:create"))],
)
async def import_quotes_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(message="Quote import is not implemented", status_code=501)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete quotes",
    dependencies=[Depends(require_permission("quotes:delete"))],
)
async def bulk_delete_quotes(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.bulk_delete_quotes(
        db, quote_ids=payload.ids, organization_id=organization_id
    )


@router.get(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Get quote details by ID",
    dependencies=[Depends(require_permission("quotes:read"))],
)
async def get_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.get_quote(db, quote_id=quote_id, organization_id=organization_id)


@router.put(
    "/{quote_id}",
    response_model=QuoteResponse,
    summary="Update quote details",
    dependencies=[Depends(require_permission("quotes:update"))],
)
async def update_quote(
    quote_id: str,
    payload: QuoteBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.update_quote(
        db, quote_id=quote_id, payload=payload, organization_id=organization_id
    )


@router.delete(
    "/{quote_id}",
    response_model=MessageResponse,
    summary="Delete quote by ID",
    dependencies=[Depends(require_permission("quotes:delete"))],
)
async def delete_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    await quote_service.delete_quote(db, quote_id=quote_id, organization_id=organization_id)
    return {"message": f"Quote {quote_id} deleted successfully", "status": "success"}


@router.post(
    "/{quote_id}/send",
    status_code=202,
    response_model=MessageResponse,
    summary="Send quote proposal email to client",
    dependencies=[Depends(require_permission("quotes:send"))],
)
async def send_quote_email(
    quote_id: str,
    recipient_email: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.send_quote(
        db,
        quote_id=quote_id,
        recipient_email=recipient_email,
        organization_id=organization_id,
    )


@router.post(
    "/{quote_id}/accept",
    response_model=MessageResponse,
    summary="Mark quote as Accepted by client",
    dependencies=[Depends(require_permission("quotes:approve"))],
)
async def accept_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.accept_quote(db, quote_id=quote_id, organization_id=organization_id)


@router.post(
    "/{quote_id}/reject",
    response_model=MessageResponse,
    summary="Reject a legacy manually-created quote",
    dependencies=[Depends(require_permission("quotes:update"))],
)
async def reject_quote(
    quote_id: str,
    reason: str | None = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.reject_quote(
        db,
        quote_id=quote_id,
        reason=reason,
        organization_id=organization_id,
    )


@router.get(
    "/{quote_id}/pdf",
    summary="Generate downloadable PDF file URL for quote",
    dependencies=[Depends(require_permission("quotes:read"))],
)
async def get_quote_pdf(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.get_quote_pdf(db, quote_id=quote_id, organization_id=organization_id)


@router.post(
    "/{quote_id}/convert-to-invoice",
    response_model=InvoiceResponse,
    summary="Convert accepted quote directly into an Invoice",
    dependencies=[Depends(require_permission("quotes:create"))],
)
async def convert_quote_to_invoice(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.convert_quote_to_invoice(
        db, quote_id=quote_id, organization_id=organization_id
    )


@router.post(
    "/{quote_id}/revisions",
    summary="Create a new revision copy of quote (v2)",
    dependencies=[Depends(require_permission("quotes:create"))],
)
async def create_quote_revision(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.create_quote_revision(
        db, quote_id=quote_id, organization_id=organization_id
    )


@router.get(
    "/{quote_id}/revisions",
    summary="List all historical revisions of quote",
    dependencies=[Depends(require_permission("quotes:read"))],
)
async def get_quote_revisions(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.get_quote_revisions(
        db, quote_id=quote_id, organization_id=organization_id
    )
