from fastapi import APIRouter
from typing import List
from app.schemas.lead import LeadCreate, LeadResponse

router = APIRouter()

@router.get("/", response_model=List[LeadResponse])
async def list_leads():
    return [
        {
          "id": "lead-1",
          "title": "Enterprise Cloud Migration",
          "company": "Acme Corp",
          "contact_name": "John Doe",
          "email": "john@acme.com",
          "phone": "+1-555-0192",
          "status": "Qualified",
          "score": 88.5,
          "organization_id": "org-1"
        }
    ]

@router.post("/", response_model=LeadResponse, status_code=201)
async def create_lead(lead: LeadCreate):
    return {
        "id": "lead-2",
        **lead.model_dump(),
        "score": 75.0,
        "organization_id": "org-1"
    }
