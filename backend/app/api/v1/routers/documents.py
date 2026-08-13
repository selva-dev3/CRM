from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    DocumentResponse,
    MessageResponse,
)
from app.services.document_service import document_service

router = APIRouter()


@router.get(
    "", response_model=List[DocumentResponse], summary="List documents with pagination"
)
async def list_documents(
    page: int = 1,
    limit: int = 20,
    folder_id: Optional[str] = None,
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, page=page, limit=limit, search=search)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload new document file to MinIO S3 storage",
)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await document_service.upload_document(db, file)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata & presigned URL",
)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    return await document_service.get_document(db, document_id)


@router.get("/{document_id}/download", summary="Get secure presigned S3 download URL")
async def download_document(document_id: str, db: AsyncSession = Depends(get_db)):
    return await document_service.download_document(db, document_id)


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete document from database & MinIO S3",
)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    return await document_service.delete_document(db, document_id)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete documents from S3",
)
async def bulk_delete_documents(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await document_service.bulk_delete(db, payload.ids)