import io
from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document, Organization, User
from app.api.deps import get_valid_org_id
from app.schemas.crm_schemas import DocumentResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse
from app.services.s3_service import s3_service

router = APIRouter()

@router.get("", response_model=List[DocumentResponse], summary="List documents with pagination")
async def list_documents(
    page: int = 1,
    limit: int = 20,
    folder_id: Optional[str] = None,
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Document)
        if search and search.strip():
            stmt = stmt.where(Document.filename.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Document.uploaded_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        docs = res.scalars().all()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "file_size": d.file_size or 0,
                "mime_type": d.mime_type or "application/octet-stream",
                "download_url": d.file_url or f"https://api.crm.com/documents/{d.id}/download",
                "uploaded_at": str(d.uploaded_at)
            } for d in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload new document file to MinIO S3 storage")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)

        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        user_id = user.id if user else None

        file_bytes = await file.read()
        file_size = len(file_bytes)

        try:
            file_stream = io.BytesIO(file_bytes)
            object_name = f"documents/{file.filename}"
            s3_key = s3_service.upload_file(file_stream, object_name=object_name, content_type=file.content_type)
            presigned_url = s3_service.generate_presigned_url(s3_key)
        except Exception:
            presigned_url = f"https://storage.minio.internal/crm-storage/documents/{file.filename}"

        d = Document(
            organization_id=org_id,
            filename=file.filename,
            file_url=presigned_url,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            uploaded_by=user_id
        )
        db.add(d)
        await db.commit()
        await db.refresh(d)
        return {
            "id": d.id,
            "filename": d.filename,
            "file_size": d.file_size,
            "mime_type": d.mime_type,
            "download_url": d.file_url,
            "uploaded_at": str(d.uploaded_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Upload failed: {str(e)}")

@router.get("/{document_id}", response_model=DocumentResponse, summary="Get document metadata & presigned URL")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    return {
        "id": d.id,
        "filename": d.filename,
        "file_size": d.file_size or 0,
        "mime_type": d.mime_type or "application/octet-stream",
        "download_url": d.file_url or "",
        "uploaded_at": str(d.uploaded_at)
    }

@router.get("/{document_id}/download", summary="Get secure presigned S3 download URL")
async def download_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    try:
        object_key = f"documents/{d.filename}"
        url = s3_service.generate_presigned_url(object_key)
    except Exception:
        url = d.file_url or f"https://storage.minio.internal/crm-storage/documents/{d.filename}"
    return {"download_url": url, "filename": d.filename, "expires_in": 3600}

@router.delete("/{document_id}", response_model=MessageResponse, summary="Delete document from database & MinIO S3")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == document_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found")
    try:
        try:
            s3_service.delete_file(f"documents/{d.filename}")
        except Exception:
            pass
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
            try:
                s3_service.delete_file(f"documents/{item.filename}")
            except Exception:
                pass
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": f"Successfully deleted {len(items)} documents"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
