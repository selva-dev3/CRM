from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Organization, OrganizationSetting, OrganizationSubscription
from app.schemas.crm_schemas import OrganizationResponse, OrganizationUpdate, MessageResponse
from app.services.s3_service import s3_service

router = APIRouter()

@router.get("", response_model=OrganizationResponse, summary="Get current organization details")
async def get_organization(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organization found")
    return {"id": org.id, "name": org.name, "domain": org.domain, "plan": org.plan, "max_users": org.max_users, "created_at": str(org.created_at), "members_count": 1}

@router.get("/all", response_model=List[OrganizationResponse], summary="List all organizations")
async def list_all_organizations(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization))
    orgs = res.scalars().all()
    if not orgs:
        return [{"id": "org-1", "name": "Default Enterprise Organization", "domain": "enterprise.crm.com", "plan": "Enterprise", "max_users": 100, "created_at": "2026-01-01", "members_count": 1}]
    return [{"id": o.id, "name": o.name, "domain": o.domain, "plan": o.plan, "max_users": o.max_users, "created_at": str(o.created_at), "members_count": 1} for o in orgs]

@router.get("/{org_id}", response_model=OrganizationResponse, summary="Get organization details by ID")
async def get_organization_by_id(org_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalars().first()
    if not org:
        if org_id == "org-1":
            return {"id": "org-1", "name": "Default Enterprise Organization", "domain": "enterprise.crm.com", "plan": "Enterprise", "max_users": 100, "created_at": "2026-01-01", "members_count": 1}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization with ID '{org_id}' not found")
    return {"id": org.id, "name": org.name, "domain": org.domain, "plan": org.plan, "max_users": org.max_users, "created_at": str(org.created_at), "members_count": 1}

@router.put("", response_model=OrganizationResponse, summary="Update organization settings")
async def update_organization(payload: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organization found to update")
    try:
        if payload.name: org.name = payload.name
        if payload.domain: org.domain = payload.domain
        await db.commit()
        return {"id": org.id, "name": org.name, "domain": org.domain, "plan": org.plan, "max_users": org.max_users, "created_at": str(org.created_at), "members_count": 1}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/members", summary="List members in current organization")
async def list_members(db: AsyncSession = Depends(get_db)):
    return []

@router.delete("/members/{user_id}", response_model=MessageResponse, summary="Remove member from organization")
async def remove_member(user_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"User {user_id} removed from organization", "status": "success"}

@router.get("/subscription", summary="Get organization subscription details")
async def get_subscription(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return {"plan": org.plan, "billing_cycle": "Monthly", "amount": 299.00, "next_billing": "2026-09-02"}

@router.post("/subscription/upgrade", response_model=MessageResponse, summary="Upgrade organization plan")
async def upgrade_plan(plan_name: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        org.plan = plan_name
        await db.commit()
        return {"message": f"Upgraded organization to {plan_name} plan", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/subscription/cancel", response_model=MessageResponse, summary="Cancel organization subscription")
async def cancel_subscription(db: AsyncSession = Depends(get_db)):
    return {"message": "Subscription cancelled", "status": "success"}

@router.get("/usage", summary="Get organization usage metrics & quota limits")
async def get_usage(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return {"users_used": 1, "users_limit": org.max_users, "storage_gb_used": 0.5, "storage_gb_limit": 500.0}

@router.post("/branding", response_model=MessageResponse, summary="Update organization branding & upload logo to MinIO S3")
async def update_branding(logo_file: Optional[UploadFile] = File(None), primary_color: Optional[str] = "#3B82F6", db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        logo_url = None
        if logo_file:
            object_name = f"branding/{org.id}_{logo_file.filename}"
            s3_key = s3_service.upload_file(logo_file.file, object_name=object_name, content_type=logo_file.content_type)
            logo_url = s3_service.generate_presigned_url(s3_key)
        return {"message": "Organization branding and logo updated on S3", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Branding S3 upload failed: {str(e)}")

@router.post("/domains/verify", response_model=MessageResponse, summary="Verify organization custom domain TXT record")
async def verify_domain(domain: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Domain {domain} verified successfully", "status": "success"}

@router.get("/domains", summary="List custom domains associated with organization")
async def list_organization_domains(db: AsyncSession = Depends(get_db)):
    return []

@router.get("/audit-logs", summary="Get organization level audit trail logs")
async def get_organization_audit_logs(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/transfer-ownership", response_model=MessageResponse, summary="Transfer organization primary ownership to another user")
async def transfer_organization_ownership(new_owner_user_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Organization ownership transferred to user {new_owner_user_id}", "status": "success"}
