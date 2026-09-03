from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    DealCreate,
    DealResponse,
    DealUpdate,
    InvoiceResponse,
    MessageResponse,
    NoteResponse,
    ProductResponse,
    QuoteResponse,
)
from app.services.deal_service import deal_service
from app.services.invoice_service import invoice_service
from app.services.org_service import organization_service

router = APIRouter()


@router.get(
    "",
    response_model=list[DealResponse],
    summary="List all deals with pagination & filters",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def list_deals(
    page: int = 1,
    limit: int = 20,
    stage: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await deal_service.list_deals(
        db, organization_id=organization_id, page=page, limit=limit, search=search, stage=stage
    )


@router.post(
    "",
    response_model=DealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new deal",
    dependencies=[Depends(require_permission("deals:create"))],
)
async def create_deal(
    payload: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    return await deal_service.create_deal(db, payload, current_user)


@router.get(
    "/stages",
    summary="Get deal pipeline stages configuration",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_stages(db: AsyncSession = Depends(get_db)):
    return await deal_service.get_deal_stages(db)


@router.post(
    "/stages",
    response_model=MessageResponse,
    summary="Create new pipeline stage",
    dependencies=[Depends(require_permission("deals:pipeline"))],
)
async def create_deal_stage(name: str, probability: float, db: AsyncSession = Depends(get_db)):
    return await deal_service.create_deal_stage(db, name=name, probability=probability)


@router.get(
    "/kanban",
    summary="Get aggregated Kanban board layout by stage",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_kanban_board(db: AsyncSession = Depends(get_db)):
    return await deal_service.get_kanban_board(db)


@router.get(
    "/win-loss-analytics",
    summary="Get win/loss ratio & reason breakdown",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_win_loss_analytics(db: AsyncSession = Depends(get_db)):
    return await deal_service.get_win_loss_analytics()


@router.get(
    "/export/csv",
    summary="Export deals list as CSV",
    dependencies=[Depends(require_permission("deals:export"))],
)
async def export_deals_csv(db: AsyncSession = Depends(get_db)):
    return await deal_service.export_deals_csv()


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import deals from CSV",
    dependencies=[Depends(require_permission("deals:import"))],
)
async def import_deals_csv(db: AsyncSession = Depends(get_db)):
    return await deal_service.import_deals_csv()


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete deals",
    dependencies=[Depends(require_permission("deals:bulk_delete"))],
)
async def bulk_delete_deals(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await deal_service.bulk_delete(db, payload.ids)


@router.post(
    "/bulk-update-stage",
    response_model=BulkActionResponse,
    summary="Bulk update deal stage",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def bulk_update_deal_stage(
    payload: BulkDeleteRequest, stage: str, db: AsyncSession = Depends(get_db)
):
    return await deal_service.bulk_update_stage(db, payload.ids, stage)


@router.get(
    "/{deal_id}",
    response_model=DealResponse,
    summary="Get deal details by ID",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.get_deal(db, deal_id)


@router.put(
    "/{deal_id}",
    response_model=DealResponse,
    summary="Update deal details by ID",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def update_deal(deal_id: str, payload: DealUpdate, db: AsyncSession = Depends(get_db)):
    return await deal_service.update_deal(db, deal_id, payload)


@router.delete(
    "/{deal_id}",
    response_model=MessageResponse,
    summary="Delete deal by ID",
    dependencies=[Depends(require_permission("deals:delete"))],
)
async def delete_deal(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.delete_deal(db, deal_id)


@router.post(
    "/{deal_id}/stage",
    response_model=MessageResponse,
    summary="Update deal pipeline stage (drag and drop)",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def update_deal_stage(deal_id: str, stage: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.update_deal_stage(db, deal_id, stage)


@router.post(
    "/{deal_id}/win",
    response_model=MessageResponse,
    summary="Mark deal as Closed Won",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def mark_deal_won(
    deal_id: str, final_amount: float | None = None, db: AsyncSession = Depends(get_db)
):
    return await deal_service.mark_deal_won(db, deal_id, final_amount)


@router.post(
    "/{deal_id}/lose",
    response_model=MessageResponse,
    summary="Mark deal as Closed Lost",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def mark_deal_lost(deal_id: str, reason: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.mark_deal_lost(db, deal_id, reason)


@router.post(
    "/{deal_id}/assign",
    response_model=MessageResponse,
    summary="Assign deal to sales rep",
    dependencies=[Depends(require_permission("deals:assign"))],
)
async def assign_deal(deal_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.assign_deal(db, deal_id, user_id)


@router.get(
    "/{deal_id}/products",
    response_model=list[ProductResponse],
    summary="List products attached to deal",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_products(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.get_deal_products(db, deal_id)


@router.post(
    "/{deal_id}/products",
    response_model=MessageResponse,
    summary="Add product item to deal",
    dependencies=[Depends(require_permission("deals:create"))],
)
async def add_deal_product(
    deal_id: str,
    product_id: str,
    quantity: int = 1,
    unit_price: float | None = None,
    custom_name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await deal_service.add_deal_product(
        db,
        deal_id=deal_id,
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        custom_name=custom_name,
    )


@router.delete(
    "/{deal_id}/products/{product_id}",
    response_model=MessageResponse,
    summary="Remove product item from deal",
    dependencies=[Depends(require_permission("deals:delete"))],
)
async def remove_deal_product(deal_id: str, product_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.remove_deal_product(db, deal_id=deal_id, product_id=product_id)


@router.get(
    "/{deal_id}/timeline",
    summary="Get deal stage history timeline",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_timeline(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.get_deal_timeline(db, deal_id)


@router.get(
    "/{deal_id}/notes",
    response_model=list[NoteResponse],
    summary="List notes for deal",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_notes(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await deal_service.get_deal_notes(db, deal_id, current_user)


@router.post(
    "/{deal_id}/notes",
    response_model=NoteResponse,
    summary="Add note to deal",
    dependencies=[Depends(require_permission("deals:create"))],
)
async def add_deal_note(
    deal_id: str,
    content: str | None = Query(None),
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note_content = content
    if not note_content and isinstance(payload, dict):
        note_content = payload.get("content")
    return await deal_service.add_deal_note(
        db, deal_id=deal_id, content=note_content, current_user=current_user
    )


@router.get(
    "/{deal_id}/quotes",
    response_model=list[QuoteResponse],
    summary="List quotes created for deal",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_quotes(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await deal_service.get_deal_quotes(db, deal_id, organization_id)


@router.post(
    "/{deal_id}/predict-win-rate",
    summary="AI prediction for deal win probability using OpenAI",
    dependencies=[Depends(require_permission("deals:update"))],
)
async def predict_deal_win_rate(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await deal_service.predict_deal_win_rate(db, deal_id, current_user)


@router.post(
    "/{deal_id}/clone",
    response_model=DealResponse,
    summary="Clone an existing deal",
    dependencies=[Depends(require_permission("deals:create"))],
)
async def clone_deal(deal_id: str, new_title: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.clone_deal(db, deal_id=deal_id, new_title=new_title)


@router.get(
    "/{deal_id}/commission",
    summary="Calculate sales rep commission split for deal",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_commission(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await deal_service.get_deal_commission(db, deal_id)


@router.post(
    "/{deal_id}/invoice",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice from a Closed Won deal (idempotent)",
    dependencies=[Depends(require_permission("invoices:create"))],
)
async def create_invoice_from_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a Closed Won deal into a Draft invoice.

    Business rule: normal invoices can only be created once the deal is
    'Closed Won'. Totals are computed server-side from the deal's billable
    line items; repeated calls return the existing invoice (unique index
    enforced at DB level).
    """
    return await invoice_service.create_invoice_from_deal(db, deal_id, current_user)


@router.get(
    "/{deal_id}/invoices",
    response_model=list[InvoiceResponse],
    summary="List invoices created from this deal",
    dependencies=[Depends(require_permission("deals:read"))],
)
async def get_deal_invoices(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.list_invoices_for_deal(
        db, deal_id=deal_id, organization_id=organization_id
    )
