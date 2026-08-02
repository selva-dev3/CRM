from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import (
    LeadResponse, LeadCreate, LeadUpdate, LeadConvertRequest, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    NoteResponse, NoteBase, TaskResponse, TaskCreate, EmailResponse, EmailSendRequest, CallLogResponse, CallLogBase, DocumentResponse
)

router = APIRouter()

@router.get("", response_model=List[LeadResponse], summary="List all leads with pagination & search")
async def list_leads(page: int = 1, limit: int = 20, search: Optional[str] = None, status: Optional[str] = None):
    return [
        {"id": "ld-101", "title": "VP of Tech", "company": "TechCorp", "contact_name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "status": "New", "source": "Website", "score": 88.5, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"},
        {"id": "ld-102", "title": "Director Ops", "company": "GlobalSolutions", "contact_name": "Bob Marley", "email": "bob@globalsolutions.com", "phone": "+1987654321", "status": "Contacted", "source": "LinkedIn", "score": 74.0, "assigned_to": "usr-2", "organization_id": "org-1", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, summary="Create a new lead")
async def create_lead(payload: LeadCreate):
    return {"id": "ld-103", "title": payload.title, "company": payload.company, "contact_name": payload.contact_name, "email": payload.email, "phone": payload.phone, "status": payload.status, "source": payload.source, "score": 85.0, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.get("/sources", summary="Get all lead sources")
async def get_lead_sources():
    return ["Website", "LinkedIn", "Referral", "Cold Call", "Event", "Partner"]

@router.post("/sources", response_model=MessageResponse, summary="Create new lead source")
async def create_lead_source(source_name: str):
    return {"message": f"Lead source {source_name} created", "status": "success"}

@router.get("/statuses", summary="Get all lead status stages")
async def get_lead_statuses():
    return ["New", "Contacted", "Qualified", "Unqualified", "Converted"]

@router.post("/statuses", response_model=MessageResponse, summary="Create new lead status stage")
async def create_lead_status(status_name: str):
    return {"message": f"Lead status {status_name} created", "status": "success"}

@router.post("/check-duplicates", summary="Check duplicate lead by email or phone")
async def check_duplicate_lead(email: str, phone: Optional[str] = None):
    return {"is_duplicate": False, "matched_lead_id": None}

@router.get("/analytics/by-source", summary="Get lead conversion analytics by source")
async def lead_analytics_by_source():
    return [{"source": "Website", "total": 120, "converted": 35}]

@router.get("/export/csv", summary="Export leads list as CSV")
async def export_leads_csv():
    return {"download_url": "https://api.crm.com/exports/leads.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import leads from CSV file")
async def import_leads_csv():
    return {"message": "Imported 45 leads successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete leads")
async def bulk_delete_leads(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Leads deleted successfully"}

@router.post("/bulk-assign", response_model=BulkActionResponse, summary="Bulk assign leads to sales rep")
async def bulk_assign_leads(payload: BulkDeleteRequest, user_id: str):
    return {"affected_count": len(payload.ids), "message": f"Leads assigned to {user_id}"}

@router.post("/bulk-update-status", response_model=BulkActionResponse, summary="Bulk update lead status")
async def bulk_update_lead_status(payload: BulkDeleteRequest, status: str):
    return {"affected_count": len(payload.ids), "message": f"Status updated to {status}"}

@router.get("/{lead_id}", response_model=LeadResponse, summary="Get lead details by ID")
async def get_lead(lead_id: str):
    return {"id": lead_id, "title": "VP of Tech", "company": "TechCorp", "contact_name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "status": "New", "source": "Website", "score": 88.5, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.put("/{lead_id}", response_model=LeadResponse, summary="Update lead by ID")
async def update_lead(lead_id: str, payload: LeadUpdate):
    return {"id": lead_id, "title": payload.title or "VP of Tech", "company": payload.company or "TechCorp", "contact_name": payload.contact_name or "Alice Johnson", "email": payload.email or "alice@techcorp.com", "phone": "+1234567890", "status": payload.status or "New", "source": "Website", "score": payload.score or 88.5, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.delete("/{lead_id}", response_model=MessageResponse, summary="Delete lead by ID")
async def delete_lead(lead_id: str):
    return {"message": f"Lead {lead_id} deleted successfully", "status": "success"}

@router.post("/{lead_id}/convert", summary="Convert lead to Deal, Contact, and Company")
async def convert_lead(lead_id: str, payload: LeadConvertRequest):
    return {"message": "Lead converted successfully", "contact_id": "cnt-200", "company_id": "cmp-300", "deal_id": "dl-400"}

@router.post("/{lead_id}/assign", response_model=MessageResponse, summary="Assign lead to specific sales rep")
async def assign_lead(lead_id: str, user_id: str):
    return {"message": f"Lead {lead_id} assigned to user {user_id}", "status": "success"}

@router.post("/{lead_id}/score", summary="Recalculate AI score for lead")
async def recalculate_lead_score(lead_id: str):
    return {"lead_id": lead_id, "old_score": 75.0, "new_score": 91.5, "factors": ["High company revenue", "Frequent email replies"]}

@router.get("/{lead_id}/timeline", summary="Get activity timeline for lead")
async def get_lead_timeline(lead_id: str):
    return [{"id": "evt-1", "action": "Email Opened", "timestamp": "2026-08-02T11:00:00Z"}]

@router.get("/{lead_id}/notes", response_model=List[NoteResponse], summary="List notes attached to lead")
async def get_lead_notes(lead_id: str):
    return [{"id": "nt-1", "entity_type": "lead", "entity_id": lead_id, "content": "Interested in enterprise tier", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.post("/{lead_id}/notes", response_model=NoteResponse, summary="Add note to lead")
async def add_lead_note(lead_id: str, content: str):
    return {"id": "nt-2", "entity_type": "lead", "entity_id": lead_id, "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/{lead_id}/tasks", response_model=List[TaskResponse], summary="List tasks assigned to lead")
async def get_lead_tasks(lead_id: str):
    return [{"id": "tsk-1", "title": "Follow up call", "description": "Discuss pricing", "priority": "High", "due_date": "2026-08-05", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-08-02"}]

@router.post("/{lead_id}/tasks", response_model=TaskResponse, summary="Create task for lead")
async def create_lead_task(lead_id: str, payload: TaskCreate):
    return {"id": "tsk-2", "title": payload.title, "description": payload.description, "priority": payload.priority, "due_date": payload.due_date, "status": payload.status, "assigned_to": payload.assigned_to, "created_at": "2026-08-02"}

@router.get("/{lead_id}/emails", response_model=List[EmailResponse], summary="List emails exchanged with lead")
async def get_lead_emails(lead_id: str):
    return [{"id": "eml-1", "from_email": "usr-1@company.com", "to": ["alice@techcorp.com"], "subject": "Intro call recap", "sent_at": "2026-08-02"}]

@router.post("/{lead_id}/emails/send", response_model=EmailResponse, summary="Send email to lead")
async def send_lead_email(lead_id: str, payload: EmailSendRequest):
    return {"id": "eml-2", "from_email": "usr-1@company.com", "to": [str(x) for x in payload.to], "subject": payload.subject, "sent_at": "2026-08-02"}

@router.get("/{lead_id}/calls", response_model=List[CallLogResponse], summary="List call logs for lead")
async def get_lead_calls(lead_id: str):
    return [{"id": "cl-1", "contact_id": lead_id, "call_type": "Outbound", "duration_seconds": 240, "notes": "Positive reaction to demo", "timestamp": "2026-08-02"}]

@router.post("/{lead_id}/calls", response_model=CallLogResponse, summary="Log call with lead")
async def log_lead_call(lead_id: str, payload: CallLogBase):
    return {"id": "cl-2", "contact_id": lead_id, "call_type": payload.call_type, "duration_seconds": payload.duration_seconds, "notes": payload.notes, "timestamp": "2026-08-02"}

@router.get("/{lead_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to lead")
async def get_lead_documents(lead_id: str):
    return [{"id": "doc-1", "filename": "requirements.pdf", "file_size": 102400, "mime_type": "application/pdf", "download_url": "https://api.crm.com/docs/1.pdf", "uploaded_at": "2026-08-02"}]

@router.post("/{lead_id}/documents", response_model=DocumentResponse, summary="Attach document to lead")
async def upload_lead_document(lead_id: str, filename: str):
    return {"id": "doc-2", "filename": filename, "file_size": 204800, "mime_type": "application/pdf", "download_url": f"https://api.crm.com/docs/{filename}", "uploaded_at": "2026-08-02"}

@router.post("/{lead_id}/archive", response_model=MessageResponse, summary="Archive lead")
async def archive_lead(lead_id: str):
    return {"message": f"Lead {lead_id} archived", "status": "success"}

@router.post("/{lead_id}/unarchive", response_model=MessageResponse, summary="Unarchive lead")
async def unarchive_lead(lead_id: str):
    return {"message": f"Lead {lead_id} restored", "status": "success"}
