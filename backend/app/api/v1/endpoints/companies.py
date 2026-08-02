from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import CompanyResponse, CompanyCreate

router = APIRouter()

@router.get("/", response_model=List[CompanyResponse], summary="List all companies")
async def list_companies():
    return [
        {"id": "cmp-1", "name": "TechCorp Inc", "industry": "Software & SaaS", "website": "https://techcorp.com", "employee_count": 250, "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=CompanyResponse, status_code=201, summary="Create company profile")
async def create_company(payload: CompanyCreate):
    return {"id": "cmp-2", **payload.model_dump(), "created_at": "2026-08-02T12:00:00Z"}
