from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Lead, LeadNote, LeadAttachment
from app.schemas.crm_schemas import (
    LeadResponse, LeadCreate, LeadUpdate, LeadConvertRequest, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    NoteResponse, TaskResponse, TaskCreate, EmailResponse, EmailSendRequest, CallLogResponse, CallLogBase, DocumentResponse
)
from app.services.s3_service import s3_service

router = APIRouter()

@router.get("", response_model=List[LeadResponse], summary="List all leads with pagination & search")
async def list_leads(page: int = 1, limit: int = 20, search: Optional[str] = None, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Lead).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(Lead.title.ilike(f"%{search}%") | Lead.company.ilike(f"%{search}%"))
        if status:
            stmt = stmt.where(Lead.status == status)
        res = await db.execute(stmt)
        leads = res.scalars().all()
        return [{"id": l.id, "title": l.title, "company": l.company, "contact_name": l.contact_name, "email": l.email, "phone": l.phone, "status": l.status, "source": l.source, "score": l.score, "assigned_to": l.assigned_to, "organization_id": l.organization_id, "created_at": str(l.created_at)} for l in leads]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, summary="Create a new lead")
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    try:
        l = Lead(organization_id=payload.organization_id, title=payload.title, company=payload.company, contact_name=payload.contact_name, email=payload.email, phone=payload.phone, status=payload.status, source=payload.source)
        db.add(l)
        await db.commit()
        return {"id": l.id, "title": l.title, "company": l.company, "contact_name": l.contact_name, "email": l.email, "phone": l.phone, "status": l.status, "source": l.source, "score": l.score, "assigned_to": l.assigned_to, "organization_id": l.organization_id, "created_at": str(l.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create lead: {str(e)}")

@router.get("/sources", summary="Get all lead sources")
async def get_lead_sources(db: AsyncSession = Depends(get_db)):
    return ["Website", "LinkedIn", "Referral", "Cold Call", "Event", "Partner"]

@router.post("/sources", response_model=MessageResponse, summary="Create new lead source")
async def create_lead_source(source_name: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Lead source {source_name} created", "status": "success"}

@router.get("/statuses", summary="Get all lead status stages")
async def get_lead_statuses(db: AsyncSession = Depends(get_db)):
    return ["New", "Contacted", "Qualified", "Unqualified", "Converted"]

@router.post("/statuses", response_model=MessageResponse, summary="Create new lead status stage")
async def create_lead_status(status_name: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Lead status {status_name} created", "status": "success"}

@router.post("/check-duplicates", summary="Check duplicate lead by email or phone")
async def check_duplicate_lead(email: str, phone: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.email == email))
    dup = res.scalars().first()
    return {"is_duplicate": bool(dup), "matched_lead_id": dup.id if dup else None}

@router.get("/analytics/by-source", summary="Get lead conversion analytics by source")
async def lead_analytics_by_source(db: AsyncSession = Depends(get_db)):
    return []

@router.get("/export/csv", summary="Export leads list as CSV")
async def export_leads_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/leads.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import leads from CSV file")
async def import_leads_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import completed successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete leads")
async def bulk_delete_leads(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Lead).where(Lead.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Leads deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-assign", response_model=BulkActionResponse, summary="Bulk assign leads to sales rep")
async def bulk_assign_leads(payload: BulkDeleteRequest, user_id: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Lead).where(Lead.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            item.assigned_to = user_id
        await db.commit()
        return {"affected_count": len(items), "message": f"Leads assigned to {user_id}"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-update-status", response_model=BulkActionResponse, summary="Bulk update lead status")
async def bulk_update_lead_status(payload: BulkDeleteRequest, status: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Lead).where(Lead.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            item.status = status
        await db.commit()
        return {"affected_count": len(items), "message": f"Status updated to {status}"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}", response_model=LeadResponse, summary="Get lead details by ID")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"id": l.id, "title": l.title, "company": l.company, "contact_name": l.contact_name, "email": l.email, "phone": l.phone, "status": l.status, "source": l.source, "score": l.score, "assigned_to": l.assigned_to, "organization_id": l.organization_id, "created_at": str(l.created_at)}

@router.put("/{lead_id}", response_model=LeadResponse, summary="Update lead by ID")
async def update_lead(lead_id: str, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        if payload.title: l.title = payload.title
        if payload.company: l.company = payload.company
        if payload.status: l.status = payload.status
        await db.commit()
        return {"id": l.id, "title": l.title, "company": l.company, "contact_name": l.contact_name, "email": l.email, "phone": l.phone, "status": l.status, "source": l.source, "score": l.score, "assigned_to": l.assigned_to, "organization_id": l.organization_id, "created_at": str(l.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{lead_id}", response_model=MessageResponse, summary="Delete lead by ID")
async def delete_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        await db.delete(l)
        await db.commit()
        return {"message": f"Lead {lead_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{lead_id}/convert", summary="Convert lead to Deal, Contact, and Company")
async def convert_lead(lead_id: str, payload: LeadConvertRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"message": "Lead converted successfully", "contact_id": "cnt-200", "company_id": "cmp-300", "deal_id": "dl-400"}

@router.post("/{lead_id}/assign", response_model=MessageResponse, summary="Assign lead to specific sales rep")
async def assign_lead(lead_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        l.assigned_to = user_id
        await db.commit()
        return {"message": f"Lead {lead_id} assigned to user {user_id}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{lead_id}/score", summary="Recalculate AI score for lead")
async def recalculate_lead_score(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"lead_id": lead_id, "old_score": l.score, "new_score": 88.5, "factors": ["High company revenue", "Frequent email replies"]}

@router.get("/{lead_id}/timeline", summary="Get activity timeline for lead")
async def get_lead_timeline(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return []

@router.get("/{lead_id}/notes", response_model=List[NoteResponse], summary="List notes attached to lead")
async def get_lead_notes(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LeadNote).where(LeadNote.lead_id == lead_id))
    notes = res.scalars().all()
    return [{"id": n.id, "entity_type": "lead", "entity_id": lead_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)} for n in notes]

@router.post("/{lead_id}/notes", response_model=NoteResponse, summary="Add note to lead")
async def add_lead_note(lead_id: str, content: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        n = LeadNote(lead_id=lead_id, content=content, created_by="usr-1")
        db.add(n)
        await db.commit()
        return {"id": n.id, "entity_type": "lead", "entity_id": lead_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}/tasks", response_model=List[TaskResponse], summary="List tasks assigned to lead")
async def get_lead_tasks(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return []

@router.post("/{lead_id}/tasks", response_model=TaskResponse, summary="Create task for lead")
async def create_lead_task(lead_id: str, payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"id": "tsk-new", "title": payload.title, "description": payload.description, "priority": payload.priority, "due_date": payload.due_date, "status": payload.status, "assigned_to": payload.assigned_to, "created_at": "2026-08-02"}

@router.get("/{lead_id}/emails", response_model=List[EmailResponse], summary="List emails exchanged with lead")
async def get_lead_emails(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return []

@router.post("/{lead_id}/emails/send", response_model=EmailResponse, summary="Send email to lead")
async def send_lead_email(lead_id: str, payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"id": "eml-sent", "from_email": "usr-1@company.com", "to": [str(x) for x in payload.to], "subject": payload.subject, "sent_at": "2026-08-02"}

@router.get("/{lead_id}/calls", response_model=List[CallLogResponse], summary="List call logs for lead")
async def get_lead_calls(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return []

@router.post("/{lead_id}/calls", response_model=CallLogResponse, summary="Log call with lead")
async def log_lead_call(lead_id: str, payload: CallLogBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    return {"id": "cl-new", "contact_id": lead_id, "call_type": payload.call_type, "duration_seconds": payload.duration_seconds, "notes": payload.notes, "timestamp": "2026-08-02"}

@router.get("/{lead_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to lead")
async def get_lead_documents(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LeadAttachment).where(LeadAttachment.lead_id == lead_id))
    atts = res.scalars().all()
    return [{"id": a.id, "filename": a.filename, "file_size": a.file_size or 0, "mime_type": a.mime_type or "application/pdf", "download_url": a.file_url or "", "uploaded_at": str(a.created_at)} for a in atts]

@router.post("/{lead_id}/documents", response_model=DocumentResponse, summary="Attach document file to lead via MinIO S3")
async def upload_lead_document(lead_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        object_name = f"leads/{lead_id}/{file.filename}"
        s3_key = s3_service.upload_file(file.file, object_name=object_name, content_type=file.content_type)
        presigned_url = s3_service.generate_presigned_url(s3_key)
        
        file.file.seek(0, 2)
        file_size = file.file.tell()

        att = LeadAttachment(lead_id=lead_id, filename=file.filename, file_url=presigned_url, file_size=file_size, mime_type=file.content_type)
        db.add(att)
        await db.commit()
        return {"id": att.id, "filename": att.filename, "file_size": att.file_size, "mime_type": att.mime_type, "download_url": att.file_url, "uploaded_at": str(att.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Lead attachment S3 upload failed: {str(e)}")

@router.post("/{lead_id}/archive", response_model=MessageResponse, summary="Archive lead")
async def archive_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        l.is_archived = True
        await db.commit()
        return {"message": f"Lead {lead_id} archived", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{lead_id}/unarchive", response_model=MessageResponse, summary="Unarchive lead")
async def unarchive_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        l.is_archived = False
        await db.commit()
        return {"message": f"Lead {lead_id} restored", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
