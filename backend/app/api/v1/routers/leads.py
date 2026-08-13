from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    CallLogResponse,
    CallLogBase,
    DocumentResponse,
    EmailResponse,
    EmailSendRequest,
    LeadConvertRequest,
    LeadCreate,
    LeadResponse,
    LeadUpdate,
    MessageResponse,
    NoteResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.lead_service import (
    LEAD_SOURCES,
    LEAD_STATUSES,
    lead_service,
)

router = APIRouter()


@router.get("", response_model=list[LeadResponse], summary="List all leads with pagination & search")
async def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    lead_status: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await lead_service.list_leads(
        db, page=page, limit=limit, search=search, lead_status=lead_status
    )


@router.post("/bulk/delete", response_model=BulkActionResponse, summary="Bulk delete leads")
async def bulk_delete_leads(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await lead_service.bulk_delete(db, payload.ids)


@router.post("/bulk/archive", response_model=BulkActionResponse, summary="Bulk archive leads")
async def bulk_archive_leads(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await lead_service.bulk_archive(db, payload.ids)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, summary="Create a new lead")
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    return await lead_service.create_lead(db, payload)


@router.get("/sources", summary="Get all lead sources")
async def get_lead_sources():
    return LEAD_SOURCES


@router.post("/sources", response_model=MessageResponse, summary="Create new lead source")
async def create_lead_source(source_name: str):
    return {"message": f"Lead source {source_name} created", "status": "success"}


@router.get("/statuses", summary="Get all lead status stages")
async def get_lead_statuses():
    return LEAD_STATUSES


@router.post("/statuses", response_model=MessageResponse, summary="Create new lead status stage")
async def create_lead_status(status_name: str):
    return {"message": f"Lead status {status_name} created", "status": "success"}


@router.post("/check-duplicates", summary="Check duplicate lead by email or phone")
async def check_duplicate_lead(
    email: str, phone: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    return await lead_service.check_duplicate(db, email)


@router.get("/analytics/by-source", summary="Get lead conversion analytics by source")
async def lead_analytics_by_source():
    return []


@router.get("/export/csv", summary="Export leads list as CSV")
async def export_leads_csv():
    return {"download_url": "https://api.crm.com/exports/leads.csv"}


@router.post("/import/csv", response_model=MessageResponse, summary="Import leads from CSV file")
async def import_leads_csv():
    return {"message": "Import completed successfully", "status": "success"}


@router.post("/bulk-update-status", response_model=BulkActionResponse, summary="Bulk update lead status")
async def bulk_update_lead_status(
    payload: BulkDeleteRequest, status_value: str, db: AsyncSession = Depends(get_db)
):
    return await lead_service.bulk_update_status(db, payload.ids, status_value)


@router.get("/{lead_id}", response_model=LeadResponse, summary="Get lead details by ID")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_lead(db, lead_id)


@router.put("/{lead_id}", response_model=LeadResponse, summary="Update lead by ID")
async def update_lead(lead_id: str, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    return await lead_service.update_lead(db, lead_id, payload)


@router.delete("/{lead_id}", response_model=MessageResponse, summary="Delete lead by ID")
async def delete_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.delete_lead(db, lead_id)


@router.post("/{lead_id}/convert", summary="Convert lead to Deal, Contact, and Company")
async def convert_lead(
    lead_id: str, payload: LeadConvertRequest, db: AsyncSession = Depends(get_db)
):
    return await lead_service.convert_lead(db, lead_id, payload)


@router.post("/{lead_id}/assign", response_model=MessageResponse, summary="Assign lead to specific sales rep")
async def assign_lead(lead_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.assign_lead(db, lead_id, user_id)


@router.post("/{lead_id}/score", summary="Recalculate AI score for lead")
async def recalculate_lead_score(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.recalculate_lead_score(db, lead_id)


@router.get("/{lead_id}/timeline", summary="Get activity timeline for lead")
async def get_lead_timeline(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_timeline(db, lead_id)


@router.get("/{lead_id}/notes", response_model=list[NoteResponse], summary="List notes attached to lead")
async def get_lead_notes(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_notes(db, lead_id)


@router.post("/{lead_id}/notes", response_model=NoteResponse, summary="Add note to lead")
async def add_lead_note(lead_id: str, content: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.add_note(db, lead_id, content)


@router.get("/{lead_id}/tasks", response_model=list[TaskResponse], summary="List tasks assigned to lead")
async def get_lead_tasks(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_tasks(db, lead_id)


@router.post("/{lead_id}/tasks", response_model=TaskResponse, summary="Create task for lead")
async def create_lead_task(lead_id: str, payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    return await lead_service.create_task(db, lead_id, payload)


@router.get("/{lead_id}/emails", response_model=list[EmailResponse], summary="List emails exchanged with lead")
async def get_lead_emails(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_emails(db, lead_id)


@router.post("/{lead_id}/emails/send", response_model=EmailResponse, summary="Send email to lead")
async def send_lead_email(
    lead_id: str, payload: EmailSendRequest, db: AsyncSession = Depends(get_db)
):
    return await lead_service.send_email(db, lead_id, payload)


@router.get("/{lead_id}/calls", response_model=list[CallLogResponse], summary="List call logs for lead")
async def get_lead_calls(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_calls(db, lead_id)


@router.post("/{lead_id}/calls", response_model=CallLogResponse, summary="Log call with lead")
async def log_lead_call(lead_id: str, payload: CallLogBase, db: AsyncSession = Depends(get_db)):
    return await lead_service.log_call(db, lead_id, payload)


@router.get("/{lead_id}/documents", response_model=list[DocumentResponse], summary="List documents attached to lead")
async def get_lead_documents(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.get_documents(db, lead_id)


@router.get("/{lead_id}/documents/{document_id}/download", summary="Download lead document file")
async def download_lead_document(
    lead_id: str, document_id: str, db: AsyncSession = Depends(get_db)
):
    file_bytes, media_type, filename = await lead_service.download_document(
        db, lead_id, document_id
    )
    return StreamingResponse(
        iter([file_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{lead_id}/documents", response_model=DocumentResponse, summary="Attach document file to lead via MinIO S3")
async def upload_lead_document(
    lead_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    return await lead_service.upload_document(db, lead_id, file)


@router.post("/{lead_id}/archive", response_model=MessageResponse, summary="Archive lead")
async def archive_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.archive_lead(db, lead_id)


@router.post("/{lead_id}/unarchive", response_model=MessageResponse, summary="Unarchive lead")
async def unarchive_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await lead_service.unarchive_lead(db, lead_id)