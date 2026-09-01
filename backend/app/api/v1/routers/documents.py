from fastapi import APIRouter, Depends, File, Query, UploadFile, status
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
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    folder_id: str | None = None,
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(
        db, page=page, limit=limit, search=search, current_user=current_user
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload new document file to MinIO S3 storage",
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.upload_document(db, file, current_user=current_user)


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
