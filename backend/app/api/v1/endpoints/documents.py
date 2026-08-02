from fastapi import APIRouter, HTTPException, status, Query, UploadFile, File
from typing import List, Optional
from app.schemas.crm_schemas import DocumentResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[DocumentResponse], summary="List documents with pagination")
async def list_documents(page: int = 1, limit: int = 20, folder_id: Optional[str] = None):
    return [
        {"id": "doc-1", "filename": "MSA_Agreement_2026.pdf", "file_size": 1048576, "mime_type": "application/pdf", "download_url": "https://api.crm.com/docs/msa.pdf", "uploaded_at": "2026-08-02"},
        {"id": "doc-2", "filename": "Technical_Proposal.docx", "file_size": 524288, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "download_url": "https://api.crm.com/docs/proposal.docx", "uploaded_at": "2026-08-02"}
    ]

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload new document file")
async def upload_document(filename: str = "contract.pdf"):
    return {"id": "doc-3", "filename": filename, "file_size": 204800, "mime_type": "application/pdf", "download_url": f"https://api.crm.com/docs/{filename}", "uploaded_at": "2026-08-02"}

@router.get("/folders", summary="List document folders tree")
async def list_folders():
    return [{"id": "fld-1", "name": "Contracts"}, {"id": "fld-2", "name": "Proposals"}]

@router.post("/folders", response_model=MessageResponse, summary="Create document folder")
async def create_folder(name: str, parent_id: Optional[str] = None):
    return {"message": f"Folder '{name}' created", "status": "success"}

@router.delete("/folders/{folder_id}", response_model=MessageResponse, summary="Delete document folder")
async def delete_folder(folder_id: str):
    return {"message": f"Folder {folder_id} deleted", "status": "success"}

@router.get("/storage-stats", summary="Get total storage space used and quota limits")
async def get_storage_stats():
    return {"used_bytes": 450000000, "limit_bytes": 10737418240, "file_count": 120}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete document files")
async def bulk_delete_documents(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Documents deleted successfully"}

@router.get("/{doc_id}", response_model=DocumentResponse, summary="Get document metadata by ID")
async def get_document(doc_id: str):
    return {"id": doc_id, "filename": "MSA_Agreement_2026.pdf", "file_size": 1048576, "mime_type": "application/pdf", "download_url": "https://api.crm.com/docs/msa.pdf", "uploaded_at": "2026-08-02"}

@router.delete("/{doc_id}", response_model=MessageResponse, summary="Delete document by ID")
async def delete_document(doc_id: str):
    return {"message": f"Document {doc_id} deleted", "status": "success"}

@router.get("/{doc_id}/download", summary="Get secure pre-signed download link for document")
async def download_document(doc_id: str):
    return {"download_url": f"https://s3.amazonaws.com/crm-bucket/docs/{doc_id}.pdf?expires=3600"}

@router.post("/{doc_id}/share", summary="Generate shareable public link with optional password")
async def share_document(doc_id: str, password: Optional[str] = None, expires_in_days: int = 7):
    return {"public_url": f"https://crm.com/share/doc/{doc_id}", "expires_at": "2026-08-09"}

@router.post("/{doc_id}/move", response_model=MessageResponse, summary="Move document to target folder")
async def move_document(doc_id: str, folder_id: str):
    return {"message": f"Moved doc {doc_id} to folder {folder_id}", "status": "success"}

@router.get("/{doc_id}/versions", summary="List file version history")
async def get_document_versions(doc_id: str):
    return [{"version": 1, "filename": "MSA_v1.pdf", "uploaded_at": "2026-07-20"}, {"version": 2, "filename": "MSA_v2.pdf", "uploaded_at": "2026-08-02"}]

@router.post("/{doc_id}/esign/request", response_model=MessageResponse, summary="Send document for DocuSign e-signature")
async def request_esignature(doc_id: str, signer_email: str):
    return {"message": f"E-signature request sent to {signer_email}", "status": "success"}

@router.get("/{doc_id}/esign/status", summary="Get e-signature execution status")
async def get_esignature_status(doc_id: str):
    return {"doc_id": doc_id, "status": "Signed", "signed_at": "2026-08-02T15:30:00Z", "signer": "alice@techcorp.com"}
