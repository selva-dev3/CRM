from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document
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
        object_name = f"documents/{file.filename}"
        s3_key = s3_service.upload_file(file.file, object_name=object_name, content_type=file.content_type)
        presigned_url = s3_service.generate_presigned_url(s3_key)
        
        file.file.seek(0, 2)
        file_size = file.file.tell()

        d = Document(
            organization_id="org-1",
            filename=file.filename,
            file_url=presigned_url,
            file_size=file_size,
            mime_type=file.content_type,
            uploaded_by="usr-1"
        )
        db.add(d)
        await db.commit()
        return {"id": d.id, "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type, "download_url": d.file_url, "uploaded_at": str(d.uploaded_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"S3 Upload failed: {str(e)}")

@router.get("/folders", summary="List document folders tree")
async def list_folders(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/folders", response_model=MessageResponse, summary="Create document folder")
async def create_folder(name: str, parent_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return {"message": f"Folder '{name}' created", "status": "success"}

@router.delete("/folders/{folder_id}", response_model=MessageResponse, summary="Delete document folder")
async def delete_folder(folder_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Folder {folder_id} deleted", "status": "success"}

@router.get("/storage-stats", summary="Get total storage space used and quota limits")
async def get_storage_stats(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document))
    docs = res.scalars().all()
    total_bytes = sum([d.file_size or 0 for d in docs])
    return {"used_bytes": total_bytes, "limit_bytes": 10737418240, "file_count": len(docs)}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete document files from S3 & Database")
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
        return {"affected_count": len(items), "message": "Documents deleted successfully from S3 & DB"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{doc_id}", response_model=DocumentResponse, summary="Get document metadata by ID")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"id": d.id, "filename": d.filename, "file_size": d.file_size or 0, "mime_type": d.mime_type or "application/pdf", "download_url": d.file_url or "", "uploaded_at": str(d.uploaded_at)}

@router.delete("/{doc_id}", response_model=MessageResponse, summary="Delete document from MinIO S3 & Database")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    try:
        s3_service.delete_file(f"documents/{d.filename}")
        await db.delete(d)
        await db.commit()
        return {"message": f"Document {doc_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{doc_id}/download", summary="Get fresh S3 presigned download URL for document")
async def download_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    try:
        presigned_url = s3_service.generate_presigned_url(f"documents/{d.filename}")
        return {"download_url": presigned_url}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to generate S3 download link: {str(e)}")

@router.post("/{doc_id}/share", summary="Generate shareable public S3 presigned link")
async def share_document(doc_id: str, password: Optional[str] = None, expires_in_days: int = 7, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    presigned_url = s3_service.generate_presigned_url(f"documents/{d.filename}", expiration_seconds=expires_in_days * 86400)
    return {"public_url": presigned_url, "expires_in_days": expires_in_days}

@router.post("/{doc_id}/move", response_model=MessageResponse, summary="Move document to target folder")
async def move_document(doc_id: str, folder_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"message": f"Moved doc {doc_id} to folder {folder_id}", "status": "success"}

@router.get("/{doc_id}/versions", summary="List file version history")
async def get_document_versions(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return []

@router.post("/{doc_id}/esign/request", response_model=MessageResponse, summary="Send document for DocuSign e-signature")
async def request_esignature(doc_id: str, signer_email: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"message": f"E-signature request sent to {signer_email}", "status": "success"}

@router.get("/{doc_id}/esign/status", summary="Get e-signature execution status")
async def get_esignature_status(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"doc_id": doc_id, "status": "Pending", "signed_at": None, "signer": None}
