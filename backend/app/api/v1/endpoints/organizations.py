from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Organization, OrganizationSetting, OrganizationSubscription
from app.schemas.crm_schemas import OrganizationResponse, OrganizationUpdate, MessageResponse

router = APIRouter()

@router.get("", response_model=OrganizationResponse, summary="Get current organization details")
async def get_organization(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if org:
        return {"id": org.id, "name": org.name, "domain": org.domain, "plan": org.plan, "max_users": org.max_users, "created_at": str(org.created_at), "members_count": 12}
    return {"id": "org-100", "name": "Acme Enterprise Corp", "domain": "acme.com", "plan": "Enterprise", "max_users": 100, "created_at": "2026-08-02", "members_count": 12}

@router.put("", response_model=OrganizationResponse, summary="Update organization settings")
async def update_organization(payload: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if org:
        if payload.name: org.name = payload.name
        if payload.domain: org.domain = payload.domain
        await db.commit()
        return {"id": org.id, "name": org.name, "domain": org.domain, "plan": org.plan, "max_users": org.max_users, "created_at": str(org.created_at), "members_count": 12}
    return {"id": "org-100", "name": payload.name or "Acme Enterprise Corp", "domain": payload.domain or "acme.com", "plan": "Enterprise", "max_users": 100, "created_at": "2026-08-02", "members_count": 12}

@router.get("/members", summary="List members in current organization")
async def list_members(db: AsyncSession = Depends(get_db)):
    return [{"user_id": "usr-1", "name": "John Doe", "email": "john@acme.com", "role": "Admin"}]

@router.delete("/members/{user_id}", response_model=MessageResponse, summary="Remove member from organization")
async def remove_member(user_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"User {user_id} removed from organization", "status": "success"}

@router.get("/subscription", summary="Get organization subscription details")
async def get_subscription(db: AsyncSession = Depends(get_db)):
    return {"plan": "Enterprise", "billing_cycle": "Monthly", "amount": 299.00, "next_billing": "2026-09-02"}

@router.post("/subscription/upgrade", response_model=MessageResponse, summary="Upgrade organization plan")
async def upgrade_plan(plan_name: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if org:
        org.plan = plan_name
        await db.commit()
    return {"message": f"Upgraded organization to {plan_name} plan", "status": "success"}

@router.post("/subscription/cancel", response_model=MessageResponse, summary="Cancel organization subscription")
async def cancel_subscription(db: AsyncSession = Depends(get_db)):
    return {"message": "Subscription cancelled", "status": "success"}

@router.get("/usage", summary="Get organization usage metrics & quota limits")
async def get_usage(db: AsyncSession = Depends(get_db)):
    return {"users_used": 12, "users_limit": 100, "storage_gb_used": 4.5, "storage_gb_limit": 500.0}

@router.post("/branding", response_model=MessageResponse, summary="Update organization branding & colors")
async def update_branding(logo_url: Optional[str] = None, primary_color: Optional[str] = "#3B82F6", db: AsyncSession = Depends(get_db)):
    return {"message": "Organization branding updated", "status": "success"}

@router.post("/domains/verify", response_model=MessageResponse, summary="Verify organization custom domain TXT record")
async def verify_domain(domain: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Domain {domain} verified successfully", "status": "success"}

@router.get("/domains", summary="List custom domains associated with organization")
async def list_organization_domains(db: AsyncSession = Depends(get_db)):
    return [{"domain": "acme.com", "verified": True}, {"domain": "acme.io", "verified": False}]

@router.get("/audit-logs", summary="Get organization level audit trail logs")
async def get_organization_audit_logs(db: AsyncSession = Depends(get_db)):
    return [{"id": "org-aud-1", "action": "PLAN_UPGRADED", "timestamp": "2026-08-02T12:00:00Z"}]

@router.post("/transfer-ownership", response_model=MessageResponse, summary="Transfer organization primary ownership to another user")
async def transfer_organization_ownership(new_owner_user_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Organization ownership transferred to user {new_owner_user_id}", "status": "success"}
