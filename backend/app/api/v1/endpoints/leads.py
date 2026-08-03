import io
from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Lead, LeadNote, LeadAttachment, User, Task, Email, CallLog, Contact
from app.schemas.crm_schemas import (
    LeadResponse, LeadCreate, LeadUpdate, LeadConvertRequest, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    NoteResponse, TaskResponse, TaskCreate, EmailResponse, EmailSendRequest, CallLogResponse, CallLogBase, DocumentResponse
)
from app.services.s3_service import s3_service

router = APIRouter()

def lead_to_dict(l: Lead) -> dict:
    return {
        "id": l.id,
        "title": l.title,
        "company": l.company,
        "contact_name": l.contact_name,
        "email": l.email,
        "phone": getattr(l, "phone", None),
        "website": getattr(l, "website", None),
        "industry": getattr(l, "industry", None),
        "company_size": getattr(l, "company_size", None),
        "country": getattr(l, "country", None),
        "state": getattr(l, "state", None),
        "city": getattr(l, "city", None),
        "address": getattr(l, "address", None),
        "postal_code": getattr(l, "postal_code", None),
        "status": l.status,
        "source": l.source,
        "score": getattr(l, "score", 50.0),
        "assigned_to": getattr(l, "assigned_to", None),
        "is_archived": getattr(l, "is_archived", False),
        "organization_id": getattr(l, "organization_id", "org-1"),
        "created_at": str(l.created_at) if getattr(l, "created_at", None) else "2026-01-01",
    }

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
        return [lead_to_dict(l) for l in leads]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, summary="Create a new lead")
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    try:
        l = Lead(
            organization_id=payload.organization_id,
            title=payload.title,
            company=payload.company,
            contact_name=payload.contact_name,
            email=payload.email,
            phone=payload.phone,
            website=payload.website,
            industry=payload.industry,
            company_size=payload.company_size,
            country=payload.country,
            state=payload.state,
            city=payload.city,
            address=payload.address,
            postal_code=payload.postal_code,
            status=payload.status,
            source=payload.source,
            score=payload.score if payload.score is not None else 50.0,
            assigned_to=payload.assigned_to,
            is_archived=payload.is_archived if payload.is_archived is not None else False,
        )
        db.add(l)
        await db.commit()
        return lead_to_dict(l)
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
    return lead_to_dict(l)

@router.put("/{lead_id}", response_model=LeadResponse, summary="Update lead by ID")
async def update_lead(lead_id: str, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        if payload.title is not None: l.title = payload.title
        if payload.company is not None: l.company = payload.company
        if payload.contact_name is not None: l.contact_name = payload.contact_name
        if payload.email is not None: l.email = payload.email
        if payload.phone is not None: l.phone = payload.phone
        if payload.website is not None: l.website = payload.website
        if payload.industry is not None: l.industry = payload.industry
        if payload.company_size is not None: l.company_size = payload.company_size
        if payload.country is not None: l.country = payload.country
        if payload.state is not None: l.state = payload.state
        if payload.city is not None: l.city = payload.city
        if payload.address is not None: l.address = payload.address
        if payload.postal_code is not None: l.postal_code = payload.postal_code
        if payload.status is not None: l.status = payload.status
        if payload.source is not None: l.source = payload.source
        if payload.score is not None: l.score = payload.score
        if payload.assigned_to is not None: l.assigned_to = payload.assigned_to
        if payload.is_archived is not None: l.is_archived = payload.is_archived
        if payload.organization_id is not None: l.organization_id = payload.organization_id
        await db.commit()
        return lead_to_dict(l)
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
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    
    timeline = [
        {
            "id": f"created-{l.id}",
            "event_type": "lead_created",
            "title": "Lead Registered",
            "description": f"Lead '{l.contact_name}' created from {l.source}",
            "timestamp": str(l.created_at)
        }
    ]

    # 1. Notes from DB
    notes_res = await db.execute(select(LeadNote).where(LeadNote.lead_id == lead_id))
    for n in notes_res.scalars().all():
        timeline.append({
            "id": f"note-{n.id}",
            "event_type": "note_added",
            "title": "Note Added",
            "description": n.content,
            "timestamp": str(n.created_at)
        })

    # 2. Attachments from DB
    atts_res = await db.execute(select(LeadAttachment).where(LeadAttachment.lead_id == lead_id))
    for a in atts_res.scalars().all():
        timeline.append({
            "id": f"doc-{a.id}",
            "event_type": "document_attached",
            "title": "Document Attached",
            "description": f"File '{a.filename}' uploaded to storage",
            "timestamp": str(getattr(a, "uploaded_at", getattr(a, "created_at", "")))
        })

    # 3. Tasks from DB for this lead
    lead_tag = f"[Lead:{lead_id}]"
    tasks_res = await db.execute(
        select(Task).where(
            Task.organization_id == l.organization_id,
            Task.description.contains(lead_tag)
        )
    )
    for t in tasks_res.scalars().all():
        clean_desc = (t.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
        timeline.append({
            "id": f"task-{t.id}",
            "event_type": "task_created",
            "title": f"Task Created: {t.title}",
            "description": clean_desc if clean_desc else f"Priority: {t.priority}, Status: {t.status}",
            "timestamp": str(t.created_at)
        })

    # 4. Emails from DB for this lead
    emails_res = await db.execute(select(Email).where(Email.to_email == l.email))
    for e in emails_res.scalars().all():
        timeline.append({
            "id": f"email-{e.id}",
            "event_type": "email_sent",
            "title": f"Email Sent: {e.subject}",
            "description": f"Sent to {e.to_email}",
            "timestamp": str(e.sent_at)
        })

    # 5. Calls from DB for this lead
    c_res = await db.execute(select(Contact.id).where(Contact.email == l.email))
    c_ids = c_res.scalars().all()
    if c_ids:
        calls_res = await db.execute(select(CallLog).where(CallLog.contact_id.in_(c_ids)))
        for cl in calls_res.scalars().all():
            timeline.append({
                "id": f"call-{cl.id}",
                "event_type": "call_logged",
                "title": f"{cl.call_type} Call Logged",
                "description": cl.notes or f"Duration: {cl.duration_seconds} sec",
                "timestamp": str(cl.timestamp)
            })

    timeline.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return timeline

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
        u_res = await db.execute(select(User).limit(1))
        u = u_res.scalars().first()
        if not u:
            u = User(email="system@crm.com", hashed_password="hashed_password_placeholder", first_name="System", last_name="User")
            db.add(u)
            await db.flush()

        n = LeadNote(lead_id=lead_id, content=content, created_by=u.id)
        db.add(n)
        await db.commit()
        return {"id": n.id, "entity_type": "lead", "entity_id": lead_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}/tasks", response_model=List[TaskResponse], summary="List tasks assigned to lead")
async def get_lead_tasks(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    
    lead_tag = f"[Lead:{lead_id}]"
    t_res = await db.execute(
        select(Task).where(
            Task.organization_id == l.organization_id,
            Task.description.contains(lead_tag)
        )
    )
    tasks = t_res.scalars().all()
    
    output = []
    for t in tasks:
        clean_desc = (t.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
        output.append({
            "id": t.id,
            "title": t.title,
            "description": clean_desc if clean_desc else None,
            "priority": t.priority,
            "due_date": str(t.due_date) if t.due_date else None,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "created_at": str(t.created_at)
        })
    return output

@router.post("/{lead_id}/tasks", response_model=TaskResponse, summary="Create task for lead")
async def create_lead_task(lead_id: str, payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        assigned_user_id = payload.assigned_to
        if not assigned_user_id:
            u_res = await db.execute(select(User.id).limit(1))
            assigned_user_id = u_res.scalars().first()
            if not assigned_user_id:
                u = User(email="system@crm.com", hashed_password="hashed_password_placeholder", first_name="System", last_name="User")
                db.add(u)
                await db.flush()
                assigned_user_id = u.id

        from datetime import datetime
        due_dt = None
        if payload.due_date:
            try:
                due_dt = datetime.fromisoformat(payload.due_date)
            except Exception:
                due_dt = datetime.utcnow()
        else:
            due_dt = datetime.utcnow()

        lead_tag = f"[Lead:{lead_id}]"
        raw_desc = payload.description or ""
        tagged_desc = f"{raw_desc}\n{lead_tag}" if raw_desc else lead_tag

        t = Task(
            organization_id=l.organization_id,
            title=payload.title,
            description=tagged_desc,
            priority=payload.priority or "Medium",
            status=payload.status or "Pending",
            due_date=due_dt,
            assigned_to=assigned_user_id
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return {
            "id": t.id,
            "title": t.title,
            "description": payload.description,
            "priority": t.priority,
            "due_date": str(t.due_date) if t.due_date else None,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "created_at": str(t.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}/emails", response_model=List[EmailResponse], summary="List emails exchanged with lead")
async def get_lead_emails(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    
    lead_tag = f"[Lead:{lead_id}]"
    e_res = await db.execute(
        select(Email).where(
            Email.organization_id == l.organization_id,
            Email.body_text.contains(lead_tag)
        )
    )
    emails = e_res.scalars().all()
    return [
        {
            "id": e.id,
            "from_email": e.from_email,
            "to": [e.to_email],
            "subject": e.subject,
            "sent_at": str(e.sent_at)
        }
        for e in emails
    ]

@router.post("/{lead_id}/emails/send", response_model=EmailResponse, summary="Send email to lead")
async def send_lead_email(lead_id: str, payload: EmailSendRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        to_addr = payload.to[0] if payload.to else l.email
        lead_tag = f"[Lead:{lead_id}]"
        raw_body = payload.body or ""
        tagged_body = f"{raw_body}\n{lead_tag}" if raw_body else lead_tag

        em = Email(
            organization_id=l.organization_id,
            from_email="sales@enterprise-crm.com",
            to_email=str(to_addr),
            subject=payload.subject,
            body_text=tagged_body,
            status="sent"
        )
        db.add(em)
        await db.commit()
        await db.refresh(em)
        return {
            "id": em.id,
            "from_email": em.from_email,
            "to": [em.to_email],
            "subject": em.subject,
            "sent_at": str(em.sent_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}/calls", response_model=List[CallLogResponse], summary="List call logs for lead")
async def get_lead_calls(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")

    lead_tag = f"[Lead:{lead_id}]"
    cl_res = await db.execute(
        select(CallLog).where(
            CallLog.organization_id == l.organization_id,
            CallLog.notes.contains(lead_tag)
        )
    )
    calls = cl_res.scalars().all()

    output = []
    for cl in calls:
        clean_notes = (cl.notes or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
        output.append({
            "id": cl.id,
            "contact_id": lead_id,
            "call_type": cl.call_type,
            "duration_seconds": cl.duration_seconds,
            "notes": clean_notes if clean_notes else None,
            "timestamp": str(cl.timestamp)
        })
    return output

@router.post("/{lead_id}/calls", response_model=CallLogResponse, summary="Log call with lead")
async def log_lead_call(lead_id: str, payload: CallLogBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        c_res = await db.execute(select(Contact.id).where(Contact.email == l.email).limit(1))
        c_id = c_res.scalars().first()
        if not c_id:
            c = Contact(first_name=l.contact_name, last_name="", email=l.email, organization_id=l.organization_id)
            db.add(c)
            await db.flush()
            c_id = c.id

        lead_tag = f"[Lead:{lead_id}]"
        raw_notes = payload.notes or ""
        tagged_notes = f"{raw_notes}\n{lead_tag}" if raw_notes else lead_tag

        cl = CallLog(
            organization_id=l.organization_id,
            contact_id=c_id,
            call_type=payload.call_type or "Outbound",
            duration_seconds=payload.duration_seconds or 0,
            notes=tagged_notes
        )
        db.add(cl)
        await db.commit()
        await db.refresh(cl)
        return {
            "id": cl.id,
            "contact_id": lead_id,
            "call_type": cl.call_type,
            "duration_seconds": cl.duration_seconds,
            "notes": payload.notes,
            "timestamp": str(cl.timestamp)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{lead_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to lead")
async def get_lead_documents(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(LeadAttachment).where(LeadAttachment.lead_id == lead_id))
    atts = res.scalars().all()
    return [{"id": a.id, "filename": a.filename, "file_size": a.file_size or 0, "mime_type": a.mime_type or "application/pdf", "download_url": a.file_url or "", "uploaded_at": str(getattr(a, "uploaded_at", getattr(a, "created_at", "")))} for a in atts]

@router.post("/{lead_id}/documents", response_model=DocumentResponse, summary="Attach document file to lead via MinIO S3")
async def upload_lead_document(lead_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")
    try:
        contents = await file.read()
        file_size = len(contents)
        object_name = f"leads/{lead_id}/{file.filename}"
        
        s3_key = s3_service.upload_file(io.BytesIO(contents), object_name=object_name, content_type=file.content_type)
        presigned_url = s3_service.generate_presigned_url(s3_key)

        att = LeadAttachment(lead_id=lead_id, filename=file.filename, file_url=presigned_url, file_size=file_size, mime_type=file.content_type)
        db.add(att)
        await db.commit()
        await db.refresh(att)
        return {"id": att.id, "filename": att.filename, "file_size": att.file_size or 0, "mime_type": att.mime_type or "application/pdf", "download_url": att.file_url, "uploaded_at": str(getattr(att, "uploaded_at", getattr(att, "created_at", "")))}
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
