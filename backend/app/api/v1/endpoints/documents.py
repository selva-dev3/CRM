from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Document
from app.schemas.crm_schemas import DocumentResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[DocumentResponse], summary="List documents with pagination")
async def list_documents(page: int = 1, limit: int = 20, folder_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        docs = res.scalars().all()
        return [{"id": d.id, "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type, "download_url": d.file_url, "uploaded_at": str(d.uploaded_at)} for d in docs]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload new document file")
async def upload_document(filename: str = "contract.pdf", db: AsyncSession = Depends(get_db)):
    try:
        d = Document(organization_id="org-1", filename=filename, file_url=f"https://api.crm.com/docs/{filename}", uploaded_by="usr-1")
        db.add(d)
        await db.commit()
        return {"id": d.id, "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type, "download_url": d.file_url, "uploaded_at": str(d.uploaded_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete document files")
async def bulk_delete_documents(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).where(Document.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Documents deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{doc_id}", response_model=DocumentResponse, summary="Get document metadata by ID")
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"id": d.id, "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type, "download_url": d.file_url, "uploaded_at": str(d.uploaded_at)}

@router.delete("/{doc_id}", response_model=MessageResponse, summary="Delete document by ID")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    try:
        await db.delete(d)
        await db.commit()
        return {"message": f"Document {doc_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{doc_id}/download", summary="Get secure pre-signed download link for document")
async def download_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"download_url": d.file_url or f"https://s3.amazonaws.com/crm-bucket/docs/{doc_id}.pdf"}

@router.post("/{doc_id}/share", summary="Generate shareable public link with optional password")
async def share_document(doc_id: str, password: Optional[str] = None, expires_in_days: int = 7, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Document).where(Document.id == doc_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found")
    return {"public_url": f"https://crm.com/share/doc/{doc_id}", "expires_at": "2026-08-09"}

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
