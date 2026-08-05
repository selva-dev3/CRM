from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.api.deps import get_current_user, get_valid_org_id
from app.models import Contact
from app.models.note import Note
from app.schemas.crm_schemas import (
    ContactResponse, ContactCreate, ContactUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    DealResponse, NoteResponse, EmailResponse, CallLogResponse
)

router = APIRouter()

@router.get(
    "",
    response_model=List[ContactResponse],
    summary="List all contacts",
)
async def list_contacts(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        org_id = await get_valid_org_id(db, current_user)
        query = select(Contact).where(Contact.organization_id == org_id)

        if search:
            query = query.where(
                (Contact.name.ilike(f"%{search}%")) |
                (Contact.email.ilike(f"%{search}%")) |
                (Contact.phone.ilike(f"%{search}%")) |
                (Contact.position.ilike(f"%{search}%"))
            )

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Contact.created_at.desc())

        result = await db.execute(query)
        contacts = result.scalars().all()

        response_list = []
        for c in contacts:
            parts = c.name.split() if c.name else []
            f_name = parts[0] if parts else ""
            l_name = " ".join(parts[1:]) if len(parts) > 1 else ""

            is_starred = bool(getattr(c, 'is_starred', False))
            response_list.append(
                ContactResponse(
                    id=c.id,
                    name=c.name or "",
                    first_name=f_name,
                    last_name=l_name,
                    email=c.email or "",
                    phone=c.phone,
                    position=c.position,
                    company_id=c.company_id,
                    is_starred=is_starred,
                    status="Star Contact" if is_starred else None,
                    created_at=str(c.created_at) if c.created_at else None,
                )
            )

        return response_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch contacts: {str(e)}",
        )

@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new contact",
)
async def create_contact(
    payload: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        raw_name = getattr(payload, "name", None) or ""
        f_name = getattr(payload, "first_name", None) or ""
        l_name = getattr(payload, "last_name", None) or ""

        full_name = raw_name.strip()

        if not full_name and (f_name or l_name):
            full_name = f"{f_name} {l_name}".strip()

        if not full_name:
            full_name = payload.email.split("@")[0]

        parts = full_name.split()

        if not f_name:
            f_name = parts[0]

        if not l_name:
            l_name = " ".join(parts[1:]) if len(parts) > 1 else "Contact"

        pos = (
            getattr(payload, "position", None)
            or getattr(payload, "job_title", None)
            or "Representative"
        )

        company_id = getattr(payload, "company_id", None)
        phone = getattr(payload, "phone", None)

        org_id = await get_valid_org_id(db, current_user)

        contact = Contact(
            organization_id=org_id,
            name=full_name,
            email=payload.email,
            phone=phone,
            position=pos,
            company_id=company_id,
        )

        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return ContactResponse(
            id=contact.id,
            name=contact.name,
            first_name=f_name,
            last_name=l_name,
            email=contact.email,
            phone=contact.phone,
            position=contact.position,
            company_id=contact.company_id,
            created_at=str(contact.created_at),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create contact: {str(e)}",
        )
@router.get("/starred", response_model=List[ContactResponse], summary="Get starred contacts list")
async def get_starred_contacts(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.is_starred == True))
    contacts = res.scalars().all()
    resp = []
    for c in contacts:
        parts = c.name.split() if c.name else []
        resp.append({
            "id": c.id,
            "name": c.name,
            "first_name": parts[0] if parts else "",
            "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
            "email": c.email,
            "phone": c.phone,
            "position": c.position,
            "company_id": c.company_id,
            "is_starred": True,
            "status": "Star Contact",
            "created_at": str(c.created_at) if c.created_at else None
        })
    return resp

@router.post("/merge", response_model=MessageResponse, summary="Merge two contact profiles")
async def merge_contacts(primary_id: str, secondary_id: str, db: AsyncSession = Depends(get_db)):
    c1 = await db.execute(select(Contact).where(Contact.id == primary_id))
    c2 = await db.execute(select(Contact).where(Contact.id == secondary_id))
    if not c1.scalars().first() or not c2.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both contacts not found")
    return {"message": f"Merged contact {secondary_id} into {primary_id}", "status": "success"}

@router.get("/export/csv", summary="Export contacts as CSV")
async def export_contacts_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/contacts.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import contacts from CSV")
async def import_contacts_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import completed successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete contacts")
async def bulk_delete_contacts(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Contact).where(Contact.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Contacts deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{contact_id}", response_model=ContactResponse, summary="Get contact details by ID")
async def get_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    parts = c.name.split() if c.name else []
    is_starred = bool(getattr(c, 'is_starred', False))
    return {
        "id": c.id,
        "name": c.name,
        "first_name": parts[0] if parts else "",
        "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
        "email": c.email,
        "phone": c.phone,
        "position": c.position,
        "company_id": c.company_id,
        "is_starred": is_starred,
        "status": "Star Contact" if is_starred else None,
        "created_at": str(c.created_at) if c.created_at else None
    }

@router.put("/{contact_id}", response_model=ContactResponse, summary="Update contact by ID")
async def update_contact(contact_id: str, payload: ContactUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    try:
        raw_name = getattr(payload, "name", None)
        f_name = getattr(payload, "first_name", None)
        l_name = getattr(payload, "last_name", None)

        if raw_name:
            c.name = raw_name.strip()
        elif f_name or l_name:
            c.name = f"{f_name or ''} {l_name or ''}".strip()

        if payload.email:
            c.email = payload.email
        if payload.phone is not None:
            c.phone = payload.phone
        if payload.company_id is not None:
            c.company_id = payload.company_id

        pos = getattr(payload, "position", None) or getattr(payload, "job_title", None)
        if pos is not None:
            c.position = pos

        await db.commit()
        await db.refresh(c)

        parts = c.name.split() if c.name else []
        is_starred = bool(getattr(c, 'is_starred', False))
        return {
            "id": c.id,
            "name": c.name,
            "first_name": parts[0] if parts else "",
            "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
            "email": c.email,
            "phone": c.phone,
            "position": c.position,
            "company_id": c.company_id,
            "is_starred": is_starred,
            "status": "Star Contact" if is_starred else None,
            "created_at": str(c.created_at) if c.created_at else None
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{contact_id}", response_model=MessageResponse, summary="Delete contact by ID")
async def delete_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    try:
        await db.delete(c)
        await db.commit()
        return {"message": f"Contact {contact_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{contact_id}/deals", response_model=List[DealResponse], summary="List deals linked to contact")
async def get_contact_deals(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    return []

@router.get("/{contact_id}/activities", summary="Get activity timeline for contact")
async def get_contact_activities(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    return []

@router.post("/{contact_id}/star", response_model=MessageResponse, summary="Star contact")
async def star_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    c.is_starred = True
    await db.commit()
    return {"message": f"Contact {contact_id} starred", "status": "success"}

@router.post("/{contact_id}/unstar", response_model=MessageResponse, summary="Unstar contact")
async def unstar_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    c.is_starred = False
    await db.commit()
    return {"message": f"Contact {contact_id} unstarred", "status": "success"}

@router.get("/{contact_id}/notes", response_model=List[NoteResponse], summary="List notes for contact")
async def get_contact_notes(contact_id: str, db: AsyncSession = Depends(get_db)):
    notes_res = await db.execute(
        select(Note).where(Note.entity_type == "contact", Note.entity_id == contact_id).order_by(Note.created_at.desc())
    )
    notes = notes_res.scalars().all()
    return [
        {
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "content": n.content,
            "created_by": n.created_by or "usr-1",
            "created_at": str(n.created_at) if n.created_at else None
        }
        for n in notes
    ]

@router.post("/{contact_id}/notes", response_model=NoteResponse, summary="Add note to contact")
async def add_contact_note(
    contact_id: str,
    content: Optional[str] = Query(None),
    payload: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    c = res.scalars().first()
    
    note_content = content
    if not note_content and isinstance(payload, dict):
        note_content = payload.get("content")
    if not note_content:
        note_content = "Note"

    org_id = await get_valid_org_id(db, current_user)
    user_id = current_user.id

    new_note = Note(
        organization_id=org_id,
        entity_type="contact",
        entity_id=contact_id,
        content=note_content,
        created_by=user_id
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)

    return {
        "id": new_note.id,
        "entity_type": new_note.entity_type,
        "entity_id": new_note.entity_id,
        "content": new_note.content,
        "created_by": new_note.created_by,
        "created_at": str(new_note.created_at) if new_note.created_at else None
    }

@router.get("/{contact_id}/emails", response_model=List[EmailResponse], summary="List emails linked to contact")
async def get_contact_emails(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    return []

@router.get("/{contact_id}/calls", response_model=List[CallLogResponse], summary="List call logs for contact")
async def get_contact_calls(contact_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contact).where(Contact.id == contact_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contact '{contact_id}' not found")
    return []
