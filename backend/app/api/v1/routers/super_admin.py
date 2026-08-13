from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.organization_invitation_schemas import (
    SuperAdminOrgCreateRequest,
    SuperAdminOrgResponse
)
from app.services.invitation_service import create_superadmin_organization_flow

router = APIRouter()

@router.post(
    "/organizations",
    response_model=SuperAdminOrgResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Super Admin: Create Organization & Trigger Admin Onboarding Invitation"
)
async def create_super_admin_organization(
    payload: SuperAdminOrgCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Super Admin Flow:
    1. Create Organization
    2. Create Subscription
    3. Create Invitation
    4. Create Pending User
    5. Send Email
    6. Write Audit Log
    7. Return Organization & Invitation Token
    """
    return await create_superadmin_organization_flow(db, payload)
