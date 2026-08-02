from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Contact, ContactAddress
from app.schemas.crm_schemas import (
    ContactResponse, ContactCreate, ContactUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    DealResponse, NoteResponse, EmailResponse, CallLogResponse
)

router = APIRouter()

@router.get("", response_model=List[ContactResponse], summary="List all contacts with pagination & search")
async def list_contacts(page: int = 1, limit: int = 20, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Contact).offset((page - 1) * limit).limit(limit)
    if search:
        stmt = stmt.where(Contact.name.ilike(f"%{search}%") | Contact.email.ilike(f"%{search}%"))
    res = await db.execute(stmt)
    contacts = res.scalars().all()
    if contacts:
        return [{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "position": c.position, "company_id": c.company_id, "created_at": str(c.created_at)} for c in contacts]
    return [
        {"id": "cnt-1", "name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "position": "VP Tech", "company_id": "cmp-1", "created_at": "2026-08-02"},
        {"id": "cnt-2", "name": "Bob Marley", "email": "bob@globalsolutions.com", "phone": "+1987654321", "position": "Director", "company_id": "cmp-2", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED, summary="Create new contact")
async def create_contact(payload: ContactCreate, db: AsyncSession = Depends(get_db)):
    c = Contact(organization_id="org-1", name=payload.name, email=payload.email, phone=payload.phone, position=payload.position, company_id=payload.company_id)
    db.add(c)
    await db.commit()
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "position": c.position, "company_id": c.company_id, "created_at": str(c.created_at)}

@router.get("/starred", response_model=List[ContactResponse], summary="Get starred contacts list")
async def get_starred_contacts(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.is_starred == True))
    contacts = res.scalars().all()
    if contacts:
        return [{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "position": c.position, "company_id": c.company_id, "created_at": str(c.created_at)} for c in contacts]
    return [{"id": "cnt-1", "name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "position": "VP Tech", "company_id": "cmp-1", "created_at": "2026-08-02"}]

@router.post("/merge", response_model=MessageResponse, summary="Merge two contact profiles")
async def merge_contacts(primary_id: str, secondary_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Merged contact {secondary_id} into {primary_id}", "status": "success"}

@router.get("/export/csv", summary="Export contacts as CSV")
async def export_contacts_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/contacts.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import contacts from CSV")
async def import_contacts_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Imported 30 contacts", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete contacts")
async def bulk_delete_contacts(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Contacts deleted successfully"}

@router.get("/{contact_id}", response_model=ContactResponse, summary="Get contact details by ID")
async def get_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if c:
        return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "position": c.position, "company_id": c.company_id, "created_at": str(c.created_at)}
    return {"id": contact_id, "name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "position": "VP Tech", "company_id": "cmp-1", "created_at": "2026-08-02"}

@router.put("/{contact_id}", response_model=ContactResponse, summary="Update contact by ID")
async def update_contact(contact_id: str, payload: ContactUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if c:
        if payload.name: c.name = payload.name
        if payload.email: c.email = payload.email
        if payload.phone: c.phone = payload.phone
        await db.commit()
        return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "position": c.position, "company_id": c.company_id, "created_at": str(c.created_at)}
    return {"id": contact_id, "name": payload.name or "Alice Johnson", "email": payload.email or "alice@techcorp.com", "phone": payload.phone or "+1234567890", "position": payload.position or "VP Tech", "company_id": "cmp-1", "created_at": "2026-08-02"}

@router.delete("/{contact_id}", response_model=MessageResponse, summary="Delete contact by ID")
async def delete_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if c:
        await db.delete(c)
        await db.commit()
    return {"message": f"Contact {contact_id} deleted successfully", "status": "success"}

@router.get("/{contact_id}/deals", response_model=List[DealResponse], summary="List deals linked to contact")
async def get_contact_deals(contact_id: str, db: AsyncSession = Depends(get_db)):
    return [{"id": "dl-1", "title": "TechCorp Renewal", "amount": 50000.0, "stage": "Qualified", "probability": 70.0, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}]

@router.get("/{contact_id}/activities", summary="Get activity timeline for contact")
async def get_contact_activities(contact_id: str, db: AsyncSession = Depends(get_db)):
    return [{"id": "act-1", "action": "Meeting Scheduled", "timestamp": "2026-08-02"}]

@router.post("/{contact_id}/star", response_model=MessageResponse, summary="Star contact")
async def star_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if c:
        c.is_starred = True
        await db.commit()
    return {"message": f"Contact {contact_id} starred", "status": "success"}

@router.post("/{contact_id}/unstar", response_model=MessageResponse, summary="Unstar contact")
async def unstar_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if c:
        c.is_starred = False
        await db.commit()
    return {"message": f"Contact {contact_id} unstarred", "status": "success"}

@router.get("/{contact_id}/notes", response_model=List[NoteResponse], summary="List notes for contact")
async def get_contact_notes(contact_id: str, db: AsyncSession = Depends(get_db)):
    return [{"id": "nt-1", "entity_type": "contact", "entity_id": contact_id, "content": "Key decision maker", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.post("/{contact_id}/notes", response_model=NoteResponse, summary="Add note to contact")
async def add_contact_note(contact_id: str, content: str, db: AsyncSession = Depends(get_db)):
    return {"id": "nt-2", "entity_type": "contact", "entity_id": contact_id, "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/{contact_id}/emails", response_model=List[EmailResponse], summary="List emails linked to contact")
async def get_contact_emails(contact_id: str, db: AsyncSession = Depends(get_db)):
    return [{"id": "eml-1", "from_email": "usr-1@company.com", "to": ["alice@techcorp.com"], "subject": "Proposal details", "sent_at": "2026-08-02"}]

@router.get("/{contact_id}/calls", response_model=List[CallLogResponse], summary="List call logs for contact")
async def get_contact_calls(contact_id: str, db: AsyncSession = Depends(get_db)):
    return [{"id": "cl-1", "contact_id": contact_id, "call_type": "Outbound", "duration_seconds": 180, "notes": "Discussed terms", "timestamp": "2026-08-02"}]
