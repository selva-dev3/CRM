from fastapi import APIRouter
from app.schemas.crm_schemas import OrganizationResponse, OrganizationBase

router = APIRouter()

@router.get("/current", response_model=OrganizationResponse, summary="Get active tenant organization profile")
async def get_current_organization():
    """Retrieves tenant organization subscription and settings."""
    return {"id": "org-1", "name": "Acme Global Corp", "domain": "acme.com", "plan": "Enterprise", "max_users": 100, "created_at": "2026-08-01T00:00:00Z"}

@router.patch("/current", response_model=OrganizationResponse, summary="Update organization settings")
async def update_organization(payload: OrganizationBase):
    """Updates company organization details."""
    return {"id": "org-1", "name": payload.name, "domain": payload.domain, "plan": payload.plan, "max_users": payload.max_users, "created_at": "2026-08-01T00:00:00Z"}
