from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    MessageResponse,
    OrganizationResponse,
    OrganizationUpdate,
    SubscriptionCheckoutRequest,
    SubscriptionCheckoutResponse,
    SubscriptionCheckoutVerifyResponse,
    SubscriptionPlanResponse,
)
from app.services.organization_service import organization_domain_service
from app.services.subscription_billing_service import SubscriptionBillingService

router = APIRouter()
subscription_billing_service = SubscriptionBillingService()


@router.get(
    "",
    response_model=OrganizationResponse,
    summary="Get current organization details",
    dependencies=[Depends(require_permission("organization:read"))],
)
async def get_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.get_organization(db, current_user)


@router.get(
    "/current",
    response_model=OrganizationResponse,
    summary="Get the authenticated user's current organization",
    dependencies=[Depends(require_permission("organization:read"))],
)
async def get_current_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return await organization_domain_service.get_current_organization(db, current_user)


@router.get(
    "/members",
    summary="List members in current organization",
    dependencies=[Depends(require_permission("organization:read"))],
)
async def list_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.list_members(db, current_user)


@router.delete(
    "/members/{user_id}",
    response_model=MessageResponse,
    summary="Remove member from organization",
    dependencies=[Depends(require_permission("organization:update"))],
)
async def remove_member(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.remove_member(db, user_id, current_user)


@router.get(
    "/subscription",
    summary="Get organization subscription details",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.get_subscription(db, current_user)


@router.get(
    "/subscription/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="List all available subscription plans",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def list_subscription_plans(db: AsyncSession = Depends(get_db)):
    return await organization_domain_service.list_subscription_plans(db)


@router.post(
    "/subscription/checkout",
    response_model=SubscriptionCheckoutResponse,
    summary="Start organization subscription purchase or confirm an existing subscription upgrade",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def create_subscription_checkout(
    payload: SubscriptionCheckoutRequest,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return await subscription_billing_service.create_checkout(
        db,
        plan_slug=payload.plan_slug,
        org_id=payload.org_id,
        current_user=current_user,
        idempotency_key=str(idempotency_key),
    )


@router.get(
    "/subscription/checkout/verify",
    response_model=SubscriptionCheckoutVerifyResponse,
    summary="Read provider verification and webhook synchronization state",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def verify_subscription_checkout(
    session_id: str | None = Query(
        default=None, min_length=1, max_length=255, pattern=r"^cs_[A-Za-z0-9_]+$"
    ),
    plan_slug: str | None = Query(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$"
    ),
    org_id: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return await subscription_billing_service.verify_checkout(
        db,
        session_id=session_id,
        plan_slug=plan_slug,
        org_id=org_id,
        current_user=current_user,
    )


@router.post(
    "/subscription/webhook",
    response_model=MessageResponse,
    summary="Receive signed Stripe organization subscription events only",
)
async def handle_stripe_subscription_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await subscription_billing_service.handle_webhook(
        db,
        payload_bytes=await request.body(),
        sig_header=stripe_signature,
    )


@router.post(
    "/subscription/upgrade",
    response_model=MessageResponse,
    summary="Direct entitlement changes are disabled; use subscription checkout",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def upgrade_plan(plan_slug: str, db: AsyncSession = Depends(get_db)):
    return await organization_domain_service.upgrade_plan(db, plan_slug)


@router.post(
    "/subscription/cancel",
    response_model=MessageResponse,
    summary="Cancel organization subscription",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def cancel_subscription(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await organization_domain_service.cancel_subscription(db, current_user)


@router.post(
    "/subscription/resume",
    response_model=MessageResponse,
    summary="Resume organization subscription",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def resume_subscription(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await organization_domain_service.resume_subscription(db, current_user)


@router.get(
    "/usage",
    summary="Get organization usage metrics & quota limits",
    dependencies=[Depends(require_permission("organization:billing"))],
)
async def get_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.get_usage(db, current_user)


@router.post(
    "/branding",
    response_model=MessageResponse,
    summary="Update organization branding & upload logo to MinIO S3",
    dependencies=[Depends(require_permission("organization:branding"))],
)
async def update_branding(
    logo_file: UploadFile | None = File(None),
    primary_color: str | None = Form("#3B82F6"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.update_branding(
        db, logo_file=logo_file, primary_color=primary_color, current_user=current_user
    )


@router.post(
    "/domains/verify",
    response_model=MessageResponse,
    summary="Verify organization custom domain TXT record",
    dependencies=[Depends(require_permission("organization:domains"))],
)
async def verify_domain(
    domain: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.verify_domain(
        db, domain=domain, current_user=current_user
    )


@router.get(
    "/domains",
    summary="List custom domains associated with organization",
    dependencies=[Depends(require_permission("organization:domains"))],
)
async def list_organization_domains(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.list_organization_domains(db, current_user)


@router.get(
    "/audit-logs",
    summary="Get organization level audit trail logs",
    dependencies=[Depends(require_permission("organization:audit"))],
)
async def get_organization_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.get_organization_audit_logs(db, current_user)


@router.post(
    "/transfer-ownership",
    response_model=MessageResponse,
    summary="Transfer organization primary ownership to another user",
    dependencies=[Depends(require_permission("organization:update"))],
)
async def transfer_organization_ownership(
    new_owner_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.transfer_organization_ownership(
        db, new_owner_user_id, current_user
    )


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details by ID",
    dependencies=[Depends(require_permission("organization:read"))],
)
async def get_organization_by_id(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.get_organization_by_id(db, org_id, current_user)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization settings by ID",
    dependencies=[Depends(require_permission("organization:update"))],
)
async def update_organization_by_id(
    org_id: str,
    payload: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.update_organization_by_id(
        db, org_id, payload, current_user
    )


@router.delete(
    "/{org_id}",
    response_model=MessageResponse,
    summary="Delete organization by ID",
    dependencies=[Depends(require_permission("organization:update"))],
)
async def delete_organization_by_id(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await organization_domain_service.delete_organization_by_id(db, org_id, current_user)
