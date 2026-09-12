from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    DocumentResponse,
    MessageResponse,
)
from app.services.document_service import document_service

router = APIRouter()


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List documents with pagination",
    dependencies=[Depends(require_permission("documents:read"))],
)
async def list_documents(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    folder_id: str | None = None,
    search: str | None = Query(None),
    lead_id: str | None = Query(None),
    contact_id: str | None = Query(None),
    company_id: str | None = Query(None),
    deal_id: str | None = Query(None),
    quote_id: str | None = Query(None),
    invoice_id: str | None = Query(None),
    payment_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    relationship_filters = {
        key: value
        for key, value in {
            "lead_id": lead_id,
            "contact_id": contact_id,
            "company_id": company_id,
            "deal_id": deal_id,
            "quote_id": quote_id,
            "invoice_id": invoice_id,
            "payment_id": payment_id,
        }.items()
        if isinstance(value, str) and value
    }
    documents = await document_service.list_documents(
        db,
        page=page,
        limit=limit,
        search=search,
        current_user=current_user,
        **relationship_filters,
    )
    total = await document_service.count_documents(
        db,
        search=search,
        current_user=current_user,
        **relationship_filters,
    )
    response.headers["X-Total-Count"] = str(total)
    return documents


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload new document file to MinIO S3 storage",
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def upload_document(
    file: UploadFile = File(...),
    lead_id: str | None = Query(None),
    contact_id: str | None = Query(None),
    company_id: str | None = Query(None),
    deal_id: str | None = Query(None),
    quote_id: str | None = Query(None),
    invoice_id: str | None = Query(None),
    payment_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.upload_document(
        db,
        file,
        current_user=current_user,
        lead_id=lead_id,
        contact_id=contact_id,
        company_id=company_id,
        deal_id=deal_id,
        quote_id=quote_id,
        invoice_id=invoice_id,
        payment_id=payment_id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata & presigned URL",
    dependencies=[Depends(require_permission("documents:read"))],
)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.get_document(db, document_id, current_user=current_user)


@router.get(
    "/{document_id}/download",
    summary="Get secure presigned S3 download URL",
    dependencies=[Depends(require_permission("documents:read"))],
)
async def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.download_document(db, document_id, current_user=current_user)


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete document from database & MinIO S3",
    dependencies=[Depends(require_permission("documents:delete"))],
)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.delete_document(db, document_id, current_user=current_user)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete documents from S3",
    dependencies=[Depends(require_permission("documents:delete"))],
)
async def bulk_delete_documents(
    payload: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.bulk_delete(db, payload.ids, current_user=current_user)
