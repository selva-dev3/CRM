from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import (
    CompanyResponse, CompanyCreate, CompanyUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    ContactResponse, DealResponse, QuoteResponse, InvoiceResponse, NoteResponse, DocumentResponse
)

router = APIRouter()

@router.get("", response_model=List[CompanyResponse], summary="List companies with pagination & search")
async def list_companies(page: int = 1, limit: int = 20, search: Optional[str] = None):
    return [
        {"id": "cmp-1", "name": "TechCorp", "industry": "Technology", "website": "techcorp.com", "employee_count": 500, "created_at": "2026-08-02"},
        {"id": "cmp-2", "name": "GlobalSolutions", "industry": "Logistics", "website": "globalsolutions.com", "employee_count": 1200, "created_at": "2026-08-02"}
    ]

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED, summary="Create new company")
async def create_company(payload: CompanyCreate):
    return {"id": "cmp-3", "name": payload.name, "industry": payload.industry, "website": payload.website, "employee_count": payload.employee_count, "created_at": "2026-08-02"}

@router.post("/lookup-domain", summary="Enrich company profile using domain lookup")
async def lookup_company_domain(domain: str):
    return {"domain": domain, "name": "Enriched Corp", "industry": "Software", "employee_count": 250, "location": "San Francisco, CA"}

@router.get("/export/csv", summary="Export companies as CSV")
async def export_companies_csv():
    return {"download_url": "https://api.crm.com/exports/companies.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import companies from CSV")
async def import_companies_csv():
    return {"message": "Imported 20 companies", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete companies")
async def bulk_delete_companies(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Companies deleted successfully"}

@router.get("/{company_id}", response_model=CompanyResponse, summary="Get company details by ID")
async def get_company(company_id: str):
    return {"id": company_id, "name": "TechCorp", "industry": "Technology", "website": "techcorp.com", "employee_count": 500, "created_at": "2026-08-02"}

@router.put("/{company_id}", response_model=CompanyResponse, summary="Update company details")
async def update_company(company_id: str, payload: CompanyUpdate):
    return {"id": company_id, "name": payload.name or "TechCorp", "industry": payload.industry or "Technology", "website": payload.website or "techcorp.com", "employee_count": payload.employee_count or 500, "created_at": "2026-08-02"}

@router.delete("/{company_id}", response_model=MessageResponse, summary="Delete company by ID")
async def delete_company(company_id: str):
    return {"message": f"Company {company_id} deleted successfully", "status": "success"}

@router.get("/{company_id}/contacts", response_model=List[ContactResponse], summary="List contacts working at company")
async def get_company_contacts(company_id: str):
    return [{"id": "cnt-1", "name": "Alice Johnson", "email": "alice@techcorp.com", "phone": "+1234567890", "position": "VP Tech", "company_id": company_id, "created_at": "2026-08-02"}]

@router.get("/{company_id}/deals", response_model=List[DealResponse], summary="List deals linked to company")
async def get_company_deals(company_id: str):
    return [{"id": "dl-1", "title": "TechCorp Enterprise Deal", "amount": 120000.0, "stage": "Proposal Sent", "probability": 80.0, "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}]

@router.get("/{company_id}/hierarchy", summary="Get parent/child corporate structure")
async def get_company_hierarchy(company_id: str):
    return {"parent_company": None, "subsidiaries": [{"id": "cmp-10", "name": "TechCorp Sub Inc"}]}

@router.post("/{company_id}/parent", response_model=MessageResponse, summary="Set parent company ID")
async def set_parent_company(company_id: str, parent_id: str):
    return {"message": f"Set parent {parent_id} for company {company_id}", "status": "success"}

@router.get("/{company_id}/quotes", response_model=List[QuoteResponse], summary="List quotes generated for company")
async def get_company_quotes(company_id: str):
    return [{"id": "qt-1", "quote_number": "Q-1001", "items": [], "total_amount": 120000.0, "status": "Sent", "created_at": "2026-08-02"}]

@router.get("/{company_id}/invoices", response_model=List[InvoiceResponse], summary="List invoices billed to company")
async def get_company_invoices(company_id: str):
    return [{"id": "inv-1", "invoice_number": "INV-500", "amount": 120000.0, "status": "Paid", "due_date": "2026-08-30", "created_at": "2026-08-02"}]

@router.get("/{company_id}/notes", response_model=List[NoteResponse], summary="List notes for company")
async def get_company_notes(company_id: str):
    return [{"id": "nt-1", "entity_type": "company", "entity_id": company_id, "content": "Annual budget planning in Q3", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.post("/{company_id}/notes", response_model=NoteResponse, summary="Add note to company")
async def add_company_note(company_id: str, content: str):
    return {"id": "nt-2", "entity_type": "company", "entity_id": company_id, "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/{company_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to company")
async def get_company_documents(company_id: str):
    return [{"id": "doc-1", "filename": "MSA_Contract.pdf", "file_size": 500000, "mime_type": "application/pdf", "download_url": "https://api.crm.com/docs/msa.pdf", "uploaded_at": "2026-08-02"}]
