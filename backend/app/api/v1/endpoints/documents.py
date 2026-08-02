from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import DocumentResponse

router = APIRouter()

@router.get("/", response_model=List[DocumentResponse], summary="List uploaded document files")
async def list_documents():
    return [
        {"id": "doc-1", "filename": "SLA_Agreement_2026.pdf", "file_size": 2048500, "mime_type": "application/pdf", "download_url": "https://s3.amazonaws.com/crm-bucket/SLA_Agreement_2026.pdf", "uploaded_at": "2026-08-01T10:00:00Z"}
    ]
