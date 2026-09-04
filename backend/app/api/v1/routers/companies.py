from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    ContactResponse,
    CustomFieldDefinition,
    DealResponse,
    DocumentResponse,
    InvoiceResponse,
    MessageResponse,
    NoteResponse,
    QuoteResponse,
)
from app.services.company_service import company_service
from app.services.note_service import note_service

router = APIRouter()


@router.get(
    "",
    response_model=list[CompanyResponse],
    summary="List companies with pagination & search",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def list_companies(
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await company_service.list_companies(db, page=page, limit=limit, search=search)


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new company",
    dependencies=[Depends(require_permission("companies:create"))],
)
async def create_company(
    payload: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await company_service.create_company(db, payload, current_user)


@router.get(
    "/custom-fields",
    response_model=list[CustomFieldDefinition],
    summary="List custom fields available for companies",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def list_company_custom_fields(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await company_service.list_custom_fields(db, current_user)


@router.post(
    "/lookup-domain",
    summary="Enrich company profile using domain lookup",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def lookup_company_domain(domain: str):
    return await company_service.lookup_domain(domain)


@router.get(
    "/export/csv",
    summary="Export companies as CSV",
    dependencies=[Depends(require_permission("companies:export"))],
)
async def export_companies_csv():
    return await company_service.export_csv()


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import companies from CSV",
    dependencies=[Depends(require_permission("companies:import"))],
)
async def import_companies_csv():
    return await company_service.import_csv()


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete companies",
    dependencies=[Depends(require_permission("companies:bulk_delete"))],
)
async def bulk_delete_companies(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await company_service.bulk_delete(db, payload.ids)


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get company details by ID",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company(db, company_id)


@router.put(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update company details",
    dependencies=[Depends(require_permission("companies:update"))],
)
async def update_company(
    company_id: str, payload: CompanyUpdate, db: AsyncSession = Depends(get_db)
):
    return await company_service.update_company(db, company_id, payload)


@router.delete(
    "/{company_id}",
    response_model=MessageResponse,
    summary="Delete company by ID",
    dependencies=[Depends(require_permission("companies:delete"))],
)
async def delete_company(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.delete_company(db, company_id)


@router.get(
    "/{company_id}/contacts",
    response_model=list[ContactResponse],
    summary="List contacts working at company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_contacts(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_contacts(db, company_id)


@router.get(
    "/{company_id}/deals",
    response_model=list[DealResponse],
    summary="List deals linked to company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_deals(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_deals(db, company_id)


@router.get(
    "/{company_id}/hierarchy",
    summary="Get parent/child corporate structure",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_hierarchy(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_hierarchy(db, company_id)


@router.post(
    "/{company_id}/parent",
    response_model=MessageResponse,
    summary="Set parent company ID",
    dependencies=[Depends(require_permission("companies:update"))],
)
async def set_parent_company(company_id: str, parent_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.set_parent_company(db, company_id, parent_id)


@router.get(
    "/{company_id}/quotes",
    response_model=list[QuoteResponse],
    summary="List quotes generated for company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_quotes(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_quotes(db, company_id)


@router.get(
    "/{company_id}/invoices",
    response_model=list[InvoiceResponse],
    summary="List invoices billed to company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_invoices(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_invoices(db, company_id)


@router.get(
    "/{company_id}/notes",
    response_model=list[NoteResponse],
    summary="List notes for company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_notes(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await note_service.list_for_entity(
        db, entity_type="company", entity_id=company_id, current_user=current_user
    )


@router.post(
    "/{company_id}/notes",
    response_model=NoteResponse,
    summary="Add note to company",
    dependencies=[Depends(require_permission("companies:create"))],
)
async def add_company_note(
    company_id: str,
    content: str | None = Query(None),
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note_content = content
    if not note_content and isinstance(payload, dict):
        note_content = payload.get("content")
    if not note_content:
        note_content = "Note"
    return await note_service.add_for_entity(
        db,
        entity_type="company",
        entity_id=company_id,
        content=note_content,
        current_user=current_user,
    )


@router.get(
    "/{company_id}/documents",
    response_model=list[DocumentResponse],
    summary="List documents attached to company",
    dependencies=[Depends(require_permission("companies:read"))],
)
async def get_company_documents(company_id: str, db: AsyncSession = Depends(get_db)):
    return await company_service.get_company_documents(db, company_id)
