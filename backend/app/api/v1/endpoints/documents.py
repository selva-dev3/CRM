import io
from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document, Organization, User
from app.schemas.crm_schemas import DocumentResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse
from app.services.s3_service import s3_service

router = APIRouter()

@router.get("", response_model=List[DocumentResponse], summary="List documents with pagination")
async def list_documents(page: int = 1, limit: int = 20, folder_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        docs = res.scalars().all()
        return [{"id": d.id, "filename": d.filename, "file_size": d.file_size or 0, "mime_type": d.mime_type or "application/octet-stream", "download_url": d.file_url or "", "uploaded_at": str(d.uploaded_at)} for d in docs]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload new document file to MinIO S3 storage")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        org_res = await db.execute(select(Organization).limit(1))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Default Enterprise CRM")
            db.add(org)
            await db.flush()

        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        user_id = user.id if user else None

        file_bytes = await file.read()
        file_size = len(file_bytes)
        file_stream = io.BytesIO(file_bytes)

        object_name = f"documents/{file.filename}"
        s3_key = s3_service.upload_file(file_stream, object_name=object_name, content_type=file.content_type)
        presigned_url = s3_service.generate_presigned_url(s3_key)

        d = Document(
            organization_id=org.id,
            filename=file.filename,
            file_url=presigned_url,
            file_size=file_size,
            mime_type=file.content_type,
            uploaded_by=user_id
        )
        db.add(d)
        await db.commit()
        return {"id": d.id, "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type, "download_url": d.file_url, "uploaded_at": str(d.uploaded_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"S3 Upload failed: {str(e)}")

@router.get("/{document_id}", response_model=DocumentResponse, summary="Get document metadata & presigned URL")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    return {"id": d.id, "filename": d.filename, "file_size": d.file_size or 0, "mime_type": d.mime_type or "application/octet-stream", "download_url": d.file_url or "", "uploaded_at": str(d.uploaded_at)}

@router.get("/{document_id}/download", summary="Get secure presigned S3 download URL")
async def download_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    try:
        object_key = f"documents/{d.filename}"
        url = s3_service.generate_presigned_url(object_key)
        return {"download_url": url, "filename": d.filename, "expires_in": 3600}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{document_id}", response_model=MessageResponse, summary="Delete document from database & MinIO S3")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    try:
        s3_service.delete_file(f"documents/{d.filename}")
        await db.delete(d)
        await db.commit()
        return {"message": f"Document {document_id} deleted", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete documents from S3")
async def bulk_delete_documents(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).where(Document.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            s3_service.delete_file(f"documents/{item.filename}")
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": f"Successfully deleted {len(items)} documents"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
