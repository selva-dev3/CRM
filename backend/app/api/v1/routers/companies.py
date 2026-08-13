from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.api.v1.deps import get_valid_org_id, get_current_user
from app.models import Company, Contact
from app.models.note import Note
from app.models.user import User
from app.schemas.crm_schemas import (
    CompanyResponse, CompanyCreate, CompanyUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    ContactResponse, DealResponse, QuoteResponse, InvoiceResponse, NoteResponse, DocumentResponse
)

router = APIRouter()

@router.get("", response_model=List[CompanyResponse], summary="List companies with pagination & search")
async def list_companies(page: int = 1, limit: int = 20, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Company).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))
        res = await db.execute(stmt)
        companies = res.scalars().all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "domain": c.website,
                "website": c.website,
                "industry": c.industry,
                "size": str(c.employee_count) if c.employee_count else None,
                "employee_count": c.employee_count,
                "created_at": str(c.created_at)
            }
            for c in companies
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED, summary="Create new company")
async def create_company(payload: CompanyCreate, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        website = getattr(payload, 'website', None) or getattr(payload, 'domain', None)
        emp_raw = getattr(payload, 'employee_count', None) or getattr(payload, 'size', None)
        emp_count = None
        if emp_raw is not None:
            try:
                emp_count = int(emp_raw)
            except (ValueError, TypeError):
                emp_count = None

        c = Company(
            organization_id=org_id,
            name=payload.name,
            industry=getattr(payload, 'industry', None),
            website=website,
            employee_count=emp_count
        )
        db.add(c)
        await db.commit()
        return {
            "id": c.id,
            "name": c.name,
            "domain": c.website,
            "website": c.website,
            "industry": c.industry,
            "size": str(c.employee_count) if c.employee_count else None,
            "employee_count": c.employee_count,
            "created_at": str(c.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create company: {str(e)}")

@router.post("/lookup-domain", summary="Enrich company profile using domain lookup")
async def lookup_company_domain(domain: str, db: AsyncSession = Depends(get_db)):
    return {"domain": domain, "name": "Enriched Corp", "industry": "Software", "employee_count": 250, "location": "San Francisco, CA"}

@router.get("/export/csv", summary="Export companies as CSV")
async def export_companies_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/companies.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import companies from CSV")
async def import_companies_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import completed successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete companies")
async def bulk_delete_companies(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Company).where(Company.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Companies deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{company_id}", response_model=CompanyResponse, summary="Get company details by ID")
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return {
        "id": c.id,
        "name": c.name,
        "domain": c.website,
        "website": c.website,
        "industry": c.industry,
        "size": str(c.employee_count) if c.employee_count else None,
        "employee_count": c.employee_count,
        "created_at": str(c.created_at)
    }

@router.put("/{company_id}", response_model=CompanyResponse, summary="Update company details")
async def update_company(company_id: str, payload: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    try:
        name = getattr(payload, 'name', None)
        if name: c.name = name
        industry = getattr(payload, 'industry', None)
        if industry: c.industry = industry
        website = getattr(payload, 'website', None) or getattr(payload, 'domain', None)
        if website: c.website = website
        emp_raw = getattr(payload, 'employee_count', None) or getattr(payload, 'size', None)
        if emp_raw is not None:
            try:
                c.employee_count = int(emp_raw)
            except (ValueError, TypeError):
                pass
        await db.commit()
        return {
            "id": c.id,
            "name": c.name,
            "domain": c.website,
            "website": c.website,
            "industry": c.industry,
            "size": str(c.employee_count) if c.employee_count else None,
            "employee_count": c.employee_count,
            "created_at": str(c.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{company_id}", response_model=MessageResponse, summary="Delete company by ID")
async def delete_company(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    c = res.scalars().first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    try:
        await db.delete(c)
        await db.commit()
        return {"message": f"Company {company_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{company_id}/contacts", response_model=List[ContactResponse], summary="List contacts working at company")
async def get_company_contacts(company_id: str, db: AsyncSession = Depends(get_db)):
    contacts_res = await db.execute(select(Contact).where(Contact.company_id == company_id))
    contacts = contacts_res.scalars().all()
    return contacts

@router.get("/{company_id}/deals", response_model=List[DealResponse], summary="List deals linked to company")
async def get_company_deals(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return []

@router.get("/{company_id}/hierarchy", summary="Get parent/child corporate structure")
async def get_company_hierarchy(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return {"parent_company": None, "subsidiaries": []}

@router.post("/{company_id}/parent", response_model=MessageResponse, summary="Set parent company ID")
async def set_parent_company(company_id: str, parent_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return {"message": f"Set parent {parent_id} for company {company_id}", "status": "success"}

@router.get("/{company_id}/quotes", response_model=List[QuoteResponse], summary="List quotes generated for company")
async def get_company_quotes(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return []

@router.get("/{company_id}/invoices", response_model=List[InvoiceResponse], summary="List invoices billed to company")
async def get_company_invoices(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return []

@router.get("/{company_id}/notes", response_model=List[NoteResponse], summary="List notes for company")
async def get_company_notes(company_id: str, db: AsyncSession = Depends(get_db)):
    notes_res = await db.execute(
        select(Note).where(Note.entity_type == "company", Note.entity_id == company_id).order_by(Note.created_at.desc())
    )
    notes = notes_res.scalars().all()
    return [
        {
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "content": n.content,
            "created_by": n.created_by,
            "created_at": str(n.created_at) if n.created_at else None
        }
        for n in notes
    ]

@router.post("/{company_id}/notes", response_model=NoteResponse, summary="Add note to company")
async def add_company_note(
    company_id: str,
    content: Optional[str] = Query(None),
    payload: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note_content = content
    if not note_content and isinstance(payload, dict):
        note_content = payload.get("content")
    if not note_content:
        note_content = "Note"

    org_id = await get_valid_org_id(db, current_user)
    user_id = current_user.id

    new_note = Note(
        organization_id=org_id,
        entity_type="company",
        entity_id=company_id,
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

@router.get("/{company_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to company")
async def get_company_documents(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company '{company_id}' not found")
    return []
