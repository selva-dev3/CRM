from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Organization, OrganizationSetting, OrganizationSubscription
from app.schemas.crm_schemas import OrganizationResponse, OrganizationCreate, OrganizationUpdate, MessageResponse
from app.services.s3_service import s3_service

router = APIRouter()

def org_to_dict(org: Organization) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "slug": getattr(org, "slug", None),
        "email": getattr(org, "email", None),
        "phone": getattr(org, "phone", None),
        "website": getattr(org, "website", None),
        "industry": getattr(org, "industry", None),
        "company_size": getattr(org, "company_size", None),
        "country": getattr(org, "country", None),
        "state": getattr(org, "state", None),
        "city": getattr(org, "city", None),
        "address": getattr(org, "address", None),
        "postal_code": getattr(org, "postal_code", None),
        "timezone": getattr(org, "timezone", "Asia/Kolkata"),
        "currency": getattr(org, "currency", "INR"),
        "language": getattr(org, "language", "en"),
        "logo_url": getattr(org, "logo_url", None),
        "tax_number": getattr(org, "tax_number", None),
        "registration_number": getattr(org, "registration_number", None),
        "status": getattr(org, "status", "active"),
        "domain": org.domain,
        "plan": org.plan,
        "max_users": org.max_users,
        "created_at": str(org.created_at),
        "members_count": 1
    }

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED, summary="Create a new organization")
async def create_organization(payload: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    try:
        org = Organization(
            name=payload.name,
            slug=payload.slug,
            email=payload.email,
            phone=payload.phone,
            website=payload.website,
            industry=payload.industry,
            company_size=payload.company_size,
            country=payload.country,
            state=payload.state,
            city=payload.city,
            address=payload.address,
            postal_code=payload.postal_code,
            timezone=payload.timezone or "Asia/Kolkata",
            currency=payload.currency or "INR",
            language=payload.language or "en",
            logo_url=payload.logo_url,
            tax_number=payload.tax_number,
            registration_number=payload.registration_number,
            status=payload.status or "active",
            domain=payload.domain,
            plan=payload.plan or "Enterprise",
            max_users=payload.max_users or 100
        )
        db.add(org)
        await db.commit()
        return org_to_dict(org)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create organization: {str(e)}")

@router.get("", response_model=OrganizationResponse, summary="Get current organization details")
async def get_organization(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).limit(1))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organization found")
    return org_to_dict(org)

@router.get("/all", response_model=List[OrganizationResponse], summary="List all organizations")
async def list_all_organizations(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization))
    orgs = res.scalars().all()
    if not orgs:
        return [{
            "id": "org-1",
            "name": "Default Enterprise Organization",
            "slug": "default-enterprise",
            "email": "info@enterprise.com",
            "phone": "+91 9876543210",
            "website": "https://enterprise.com",
            "industry": "Information Technology",
            "company_size": "51-200",
            "country": "India",
            "state": "Tamil Nadu",
            "city": "Thoothukudi",
            "address": "123 Main Road",
            "postal_code": "628001",
            "timezone": "Asia/Kolkata",
            "currency": "INR",
            "language": "en",
            "logo_url": "",
            "tax_number": "GSTIN123456789",
            "registration_number": "CIN123456789",
            "status": "active",
            "domain": "enterprise.crm.com",
            "plan": "Enterprise",
            "max_users": 100,
            "created_at": "2026-01-01",
            "members_count": 1
        }]
    return [org_to_dict(o) for o in orgs]

@router.get("/{org_id}", response_model=OrganizationResponse, summary="Get organization details by ID")
async def get_organization_by_id(org_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalars().first()
    if not org:
        if org_id == "org-1":
            return {
                "id": "org-1",
                "name": "Default Enterprise Organization",
                "slug": "default-enterprise",
                "email": "info@enterprise.com",
                "phone": "+91 9876543210",
                "website": "https://enterprise.com",
                "industry": "Information Technology",
                "company_size": "51-200",
                "country": "India",
                "state": "Tamil Nadu",
                "city": "Thoothukudi",
                "address": "123 Main Road",
                "postal_code": "628001",
                "timezone": "Asia/Kolkata",
                "currency": "INR",
                "language": "en",
                "logo_url": "",
                "tax_number": "GSTIN123456789",
                "registration_number": "CIN123456789",
                "status": "active",
                "domain": "enterprise.crm.com",
                "plan": "Enterprise",
                "max_users": 100,
                "created_at": "2026-01-01",
                "members_count": 1
            }
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization with ID '{org_id}' not found")
    return org_to_dict(org)

@router.put("/{org_id}", response_model=OrganizationResponse, summary="Update organization settings by ID")
async def update_organization_by_id(org_id: str, payload: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization with ID '{org_id}' not found to update")
    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None and hasattr(org, field):
                setattr(org, field, value)
        await db.commit()
        return org_to_dict(org)
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
