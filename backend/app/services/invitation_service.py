import uuid
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import ensure_can_assign_role, is_super_admin_role, is_super_admin_user
from app.core.security import create_access_token, get_password_hash
from app.models import (
    AuditLog,
    Organization,
    OrganizationInvitation,
    OrganizationSetting,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
)
from app.schemas.organization_invitation_schemas import (
    AcceptInvitationRequest,
    CreateOrganizationInvitationRequest,
    InvitationListResponse,
    InvitationResponse,
    InvitationStatusResponse,
    InviteUserResponse,
    NewOrganizationInviteResponse,
    OrganizationInviteRequest,
)
from app.services.email_service import (
    send_organization_onboarding_invite_email,
    send_user_invite_email,
)


class InvitationPlanInfo(TypedDict):
    name: str
    slug: str
    price_monthly: int
    max_users: int
    max_storage_gb: int
    ai_credits: int


DEFAULT_PLANS_FALLBACK: dict[str, InvitationPlanInfo] = {
    "free": {
        "name": "Free",
        "slug": "free",
        "price_monthly": 0,
        "max_users": 3,
        "max_storage_gb": 5,
        "ai_credits": 50,
    },
    "starter": {
        "name": "Starter",
        "slug": "starter",
        "price_monthly": 999,
        "max_users": 10,
        "max_storage_gb": 20,
        "ai_credits": 200,
    },
    "professional": {
        "name": "Professional",
        "slug": "professional",
        "price_monthly": 2999,
        "max_users": 25,
        "max_storage_gb": 50,
        "ai_credits": 500,
    },
    "business": {
        "name": "Business",
        "slug": "business",
        "price_monthly": 7999,
        "max_users": 50,
        "max_storage_gb": 100,
        "ai_credits": 1000,
    },
    "enterprise": {
        "name": "Enterprise",
        "slug": "enterprise",
        "price_monthly": 19999,
        "max_users": 100,
        "max_storage_gb": 500,
        "ai_credits": -1,
    },
}


def _require_current_organization_id(current_user: User) -> str:
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user has no current organization",
        )
    return organization_id


def _build_invitation_response(
    inv: OrganizationInvitation, org_name: str | None = None
) -> InvitationResponse:
    invite_url = f"{settings.FRONTEND_URL}/accept-invite/organization/{inv.token}"
    expires_str = inv.expires_at.isoformat() if inv.expires_at else ""
    accepted_str = inv.accepted_at.isoformat() if inv.accepted_at else None
    created_str = inv.created_at.isoformat() if inv.created_at else ""

    return InvitationResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        organization_name=org_name,
        email=inv.email,
        full_name=inv.full_name,
        role=inv.role_id or "Admin",
        subscription_id=inv.subscription_id,
        token=inv.token,
        status=inv.status,
        expires_at=expires_str,
        accepted_at=accepted_str,
        created_at=created_str,
        invite_url=invite_url,
    )


async def _resolve_invitation_role(
    db: AsyncSession,
    current_user: User,
    role_value: str | None = "Admin",
    *,
    target_organization_id: str | None,
) -> Role:
    """Resolve and authorize the role attached to an organization invitation.

    Enforced server-side regardless of any frontend filtering:
    1. Role must exist.
    2. Role must be global or belong to the target organization. New-organization
       invitations may use global roles only.
    3. The super_admin role may only be assigned by a super_admin actor (403 otherwise).
    """
    role_str = (role_value or "").strip() or "Admin"
    ownership = (
        Role.organization_id.is_(None)
        if target_organization_id is None
        else or_(
            Role.organization_id.is_(None),
            Role.organization_id == target_organization_id,
        )
    )
    role = await db.scalar(
        select(Role).where(
            ((Role.id == role_str) | (func.lower(Role.name) == role_str.lower())),
            ownership,
        )
    )
    if not role and role_str.lower() in {"admin", "administrator"}:
        role = await db.scalar(
            select(Role).where(
                (
                    (func.lower(Role.name) == "admin")
                    | (func.lower(Role.name) == "administrator")
                ),
                ownership,
            )
        )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: '{role_value}'",
        )
    if role.organization_id is not None and role.organization_id != target_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role.name}' does not belong to the target organization",
        )
    if is_super_admin_role(role):
        ensure_can_assign_role(
            actor_is_super_admin=await is_super_admin_user(db, current_user),
            target_is_super_admin=True,
        )
    return role


async def create_new_organization_invitation(
    db: AsyncSession, payload: CreateOrganizationInvitationRequest, current_user: User
) -> NewOrganizationInviteResponse:
    """Invite Organization flow.

    Creates a brand-new organization (the ID is generated by the backend/DB — a
    client-supplied organization_id is never accepted), links a pending invitation
    to it, and emails the invitee. The organization, settings, subscription and
    invitation are created in a single transaction so a failure rolls back
    everything (no orphan organization); the email is sent only after commit.
    """
    email_clean = payload.email.strip().lower()
    full_name = payload.full_name.strip()

    # 1. Reject active users (same rule as every other invite flow)
    existing_user = await db.scalar(select(User).where(User.email.ilike(email_clean)))
    if existing_user and existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' is already an active user.",
        )

    # 2. Resolve & authorize the requested role (super_admin guard enforced here)
    role = await _resolve_invitation_role(
        db, current_user, payload.role_id, target_organization_id=None
    )
    role_name = role.name

    # 3. Create the NEW organization with a backend-generated ID
    slug_base = full_name.lower().replace(" ", "-")
    slug = f"{slug_base}-{uuid.uuid4().hex[:4]}"
    org_name = f"{full_name}'s Organization"

    org = Organization(
        id=str(uuid.uuid4()),
        name=org_name,
        slug=slug,
        domain=f"{slug}.crm.com",
        email=email_clean,
        role="Admin",
        plan="Free",
        max_users=3,
        status="active",
        is_active=True,
    )
    db.add(org)
    await db.flush()

    settings_obj = OrganizationSetting(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        timezone="Asia/Kolkata",
        currency="INR",
        language="en",
    )
    db.add(settings_obj)

    free_plan = await db.scalar(
        select(SubscriptionPlan).where(func.lower(SubscriptionPlan.slug) == "free")
    )
    sub = OrganizationSubscription(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        plan_id=free_plan.id if free_plan else None,
        status="active",
        billing_cycle="Monthly",
        amount=0.0,
        currency="INR",
        max_users=3,
        storage_limit_gb=5,
        ai_credits=50,
    )
    db.add(sub)
    await db.flush()

    # 4. Reuse a pending invitation for this email (no duplicates); otherwise create one
    token = f"inv_{uuid.uuid4().hex}"
    expires_at = datetime.now(UTC) + timedelta(hours=24)

    existing_inv = await db.scalar(
        select(OrganizationInvitation).where(
            func.lower(OrganizationInvitation.email) == email_clean,
            OrganizationInvitation.status == "Pending",
        )
    )
    if existing_inv:
        existing_inv.organization_id = org.id
        existing_inv.subscription_id = sub.id
        existing_inv.full_name = full_name
        existing_inv.role_id = role_name
        existing_inv.token = token
        existing_inv.expires_at = expires_at
        invitation = existing_inv
    else:
        invitation = OrganizationInvitation(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            subscription_id=sub.id,
            email=email_clean,
            full_name=full_name,
            role_id=role_name,
            token=token,
            status="Pending",
            expires_at=expires_at,
        )
        db.add(invitation)

    # 5. Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=current_user.id if current_user else None,
        action="CREATE_ORGANIZATION_INVITATION",
        ip_address=None,
        details=f"Created organization '{org.name}' ({org.id}) and invited '{email_clean}' as '{role_name}'.",
    )
    db.add(audit)

    # 6. Single transaction — org, settings, subscription and invitation
    #    commit (or roll back) together.
    await db.commit()
    await db.refresh(org)
    await db.refresh(sub)
    await db.refresh(invitation)

    # 7. Email AFTER commit (matches the existing invitation strategy)
    invite_url = f"{settings.FRONTEND_URL}/accept-invite/organization/{token}"
    send_user_invite_email(email_to=email_clean, role=role_name, invite_url=invite_url)

    inv_resp = _build_invitation_response(invitation, org.name)

    return NewOrganizationInviteResponse(
        organization={
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "domain": org.domain,
            "email": org.email,
            "status": org.status,
            "plan": org.plan,
            "max_users": org.max_users,
        },
        invitation=inv_resp,
        message=f"Organization '{org.name}' created and invitation sent to {email_clean}.",
    )


async def create_organization_user_invitation(
    db: AsyncSession, payload: OrganizationInviteRequest, current_user: User
) -> InviteUserResponse:
    """Invite new users via email returning only token, invite_url, and success message.

    The target organization is ALWAYS derived from the authenticated user's
    current organization — a client-supplied ``organization_id`` is never
    trusted, so an inviter cannot place another user into an organization they
    do not belong to.
    """
    target_org_id = getattr(current_user, "organization_id", None)
    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user has no current organization",
        )

    org = await db.scalar(select(Organization).where(Organization.id == target_org_id))
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current organization not found",
        )
    if getattr(org, "status", "active") != "active" or not getattr(org, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive or disabled."
        )
    sub = await db.scalar(
        select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == target_org_id
        )
    )

    # Resolve & authorize the requested role (super_admin only assignable by a super_admin actor)
    role = await _resolve_invitation_role(
        db,
        current_user,
        payload.role or "Admin",
        target_organization_id=target_org_id,
    )
    role_name = role.name

    # Check if user is already registered & active
    email_clean = payload.email.strip().lower()
    existing_user = await db.scalar(select(User).where(User.email.ilike(email_clean)))
    if existing_user and existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' is already an active user.",
        )

    # Check for existing pending invitation for this email
    existing_inv = await db.scalar(
        select(OrganizationInvitation).where(
            func.lower(OrganizationInvitation.email) == email_clean,
            OrganizationInvitation.status == "Pending",
        )
    )
    token = f"inv_{uuid.uuid4().hex}"
    expires_at = datetime.now(UTC) + timedelta(hours=24)

    if existing_inv:
        existing_inv.token = token
        existing_inv.expires_at = expires_at
        existing_inv.role_id = role_name
        existing_inv.full_name = payload.full_name or existing_inv.full_name
        existing_inv.organization_id = target_org_id
        invitation = existing_inv
    else:
        invitation = OrganizationInvitation(
            id=str(uuid.uuid4()),
            organization_id=target_org_id,
            email=email_clean,
            full_name=payload.full_name.strip() if payload.full_name else None,
            role_id=role_name,
            subscription_id=sub.id if sub else None,
            token=token,
            status="Pending",
            expires_at=expires_at,
        )
        db.add(invitation)

    # Audit Log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=target_org_id,
        user_id=current_user.id if current_user else None,
        action="CREATE_INVITATION",
        ip_address=None,
        details=f"Invitation sent to '{payload.email}'.",
    )
    db.add(audit)

    await db.commit()
    await db.refresh(invitation)

    # Send Email
    invite_url = f"{settings.FRONTEND_URL}/accept-invite/organization/{token}"
    send_user_invite_email(email_to=email_clean, role=role_name, invite_url=invite_url)

    return InviteUserResponse(
        token=token, invite_url=invite_url, message=f"Invitation sent successfully to {email_clean}"
    )


async def get_and_validate_invitation_by_token(
    db: AsyncSession, token: str
) -> InvitationStatusResponse:
    """Validate invitation token."""
    inv = await db.scalar(
        select(OrganizationInvitation).where(OrganizationInvitation.token == token.strip())
    )
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation token not found or invalid."
        )

    if inv.status == "Cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has been cancelled."
        )

    if inv.status == "Accepted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has already been accepted."
        )

    now_utc = datetime.now(UTC)
    if inv.expires_at and inv.expires_at.tzinfo is None:
        inv_expires = inv.expires_at.replace(tzinfo=UTC)
    else:
        inv_expires = inv.expires_at

    if now_utc > inv_expires:
        inv.status = "Expired"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="Invitation token has expired."
        )

    # Organization Check if already assigned
    org_dict = None
    if inv.organization_id:
        org = await db.scalar(select(Organization).where(Organization.id == inv.organization_id))
        if org and (
            getattr(org, "status", "active") != "active" or not getattr(org, "is_active", True)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive."
            )
        if org:
            org_dict = {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "domain": org.domain,
                "plan": org.plan,
                "status": org.status,
            }

    return InvitationStatusResponse(
        organization=org_dict,
        email=inv.email,
        full_name=inv.full_name,
        role=inv.role_id or "Admin",
        expires_at=inv_expires.isoformat(),
        status=inv.status,
        is_valid=True,
    )


async def accept_organization_invitation(
    db: AsyncSession, token: str, payload: AcceptInvitationRequest
) -> dict:
    """Accept invitation, collect organization details, auto-generate Organization & Org ID upon acceptance, hash password, activate user account, and return JWT token."""
    # 1. Validate invitation token
    await get_and_validate_invitation_by_token(db, token)

    inv = await db.scalar(
        select(OrganizationInvitation).where(OrganizationInvitation.token == token.strip())
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    email_clean = inv.email.strip().lower()
    full_name = payload.full_name or inv.full_name or email_clean.split("@")[0].capitalize()

    # 2. Check or Create Organization & Org ID upon Acceptance
    org = None
    if inv.organization_id:
        org = await db.scalar(select(Organization).where(Organization.id == inv.organization_id))

    requested_org_name = (payload.organization_name or "").strip()

    if org:
        # Update existing organization with user's provided onboarding details
        if requested_org_name:
            org.name = requested_org_name
            slug_base = requested_org_name.lower().replace(" ", "-")
            org.slug = f"{slug_base}-{uuid.uuid4().hex[:4]}"
        if payload.domain and payload.domain.strip():
            org.domain = payload.domain.strip()
        if payload.phone and payload.phone.strip():
            org.phone = payload.phone.strip()
        if payload.industry and payload.industry.strip():
            org.industry = payload.industry.strip()
        if payload.country and payload.country.strip():
            org.country = payload.country.strip()
        if payload.city and payload.city.strip():
            org.city = payload.city.strip()
    else:
        # Create brand new Organization with auto-generated ID
        auto_org_id = f"org_{uuid.uuid4().hex[:12]}"
        org_name = requested_org_name if requested_org_name else f"{full_name}'s Organization"
        slug_base = org_name.lower().replace(" ", "-")
        slug = f"{slug_base}-{uuid.uuid4().hex[:4]}"
        domain = (
            payload.domain.strip()
            if (payload.domain and payload.domain.strip())
            else f"{slug}.crm.com"
        )

        org = Organization(
            id=auto_org_id,
            name=org_name,
            slug=slug,
            domain=domain,
            email=email_clean,
            phone=payload.phone.strip() if payload.phone else None,
            industry=payload.industry.strip() if payload.industry else "Technology",
            country=payload.country.strip() if payload.country else "India",
            city=payload.city.strip() if payload.city else None,
            status="active",
            is_active=True,
            plan="Free",
            max_users=3,
        )
        db.add(org)
        await db.flush()

        settings_obj = OrganizationSetting(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            timezone="Asia/Kolkata",
            currency="INR",
            language="en",
        )
        db.add(settings_obj)

        sub = OrganizationSubscription(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            status="active",
            billing_cycle="Monthly",
            amount=0.0,
            currency="INR",
            max_users=3,
            storage_limit_gb=5,
        )
        db.add(sub)
        await db.flush()

        inv.organization_id = org.id
        inv.subscription_id = sub.id

    # 3. Find or Create User
    user = await db.scalar(select(User).where(User.email.ilike(email_clean)))
    hashed_pwd = get_password_hash(payload.password)

    if user:
        user.hashed_password = hashed_pwd
        user.name = full_name
        user.organization_id = org.id
        user.role = inv.role_id or "Admin"
        user.is_active = True
        user.is_verified = True
    else:
        user = User(
            id=str(uuid.uuid4()),
            name=full_name,
            email=email_clean,
            hashed_password=hashed_pwd,
            role=inv.role_id or "Admin",
            organization_id=org.id,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

    # 4. Update Invitation Record
    inv.status = "Accepted"
    inv.accepted_at = datetime.now(UTC)

    # 5. Audit Log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=user.id,
        action="ACCEPT_INVITATION",
        ip_address=None,
        details=f"Invitation accepted by '{user.email}' and Organization '{org.name}' ({org.id}) activated.",
    )
    db.add(audit)

    await db.commit()
    await db.refresh(user)

    # 6. Generate JWT Token
    access_token = create_access_token(subject=user.id, expires_delta=timedelta(days=7))

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "is_active": user.is_active,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "domain": org.domain,
            "plan": org.plan,
        },
        "message": f"Invitation accepted! Organization '{org.name}' created with ID '{org.id}' and account activated successfully.",
    }


async def resend_organization_invitation(
    db: AsyncSession, invitation_id: str, current_user: User
) -> InvitationResponse:
    """Generate new token, expire old token, send email again."""
    organization_id = _require_current_organization_id(current_user)
    inv = await db.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
        )
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if inv.status == "Accepted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resend an already accepted invitation.",
        )

    org = await db.scalar(select(Organization).where(Organization.id == inv.organization_id))

    new_token = f"inv_{uuid.uuid4().hex}"
    inv.token = new_token
    inv.expires_at = datetime.now(UTC) + timedelta(hours=24)
    inv.status = "Pending"

    audit = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=inv.organization_id,
        user_id=current_user.id,
        action="RESEND_INVITATION",
        details=f"Resent invitation email to '{inv.email}' by '{current_user.email}'.",
    )
    db.add(audit)

    await db.commit()
    await db.refresh(inv)

    send_organization_onboarding_invite_email(
        email_to=inv.email,
        admin_name=inv.full_name or "Admin",
        organization_name=org.name if org else "CRM Organization",
        plan_name="Enterprise",
        token=new_token,
        expires_at_str="24 Hours",
    )

    return _build_invitation_response(inv, org.name if org else None)


async def cancel_organization_invitation(
    db: AsyncSession, invitation_id: str, current_user: User
) -> dict:
    """Cancel an invitation."""
    organization_id = _require_current_organization_id(current_user)
    inv = await db.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
        )
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if inv.status == "Accepted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel an already accepted invitation.",
        )

    inv.status = "Cancelled"

    audit = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=inv.organization_id,
        user_id=current_user.id,
        action="CANCEL_INVITATION",
        details=f"Cancelled invitation for '{inv.email}' by '{current_user.email}'.",
    )
    db.add(audit)

    await db.commit()
    return {
        "message": f"Invitation for '{inv.email}' cancelled successfully.",
        "status": "Cancelled",
    }


async def list_organization_invitations(
    db: AsyncSession,
    current_user: User,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
) -> InvitationListResponse:
    """List invitations with search, status filter, pagination, and sorting."""
    organization_id = _require_current_organization_id(current_user)
    query = select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == organization_id
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                OrganizationInvitation.email.ilike(term),
                OrganizationInvitation.full_name.ilike(term),
            )
        )

    if status_filter and status_filter.strip() and status_filter.lower() != "all":
        query = query.where(
            func.lower(OrganizationInvitation.status) == status_filter.strip().lower()
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    # Sorting
    if sort_by == "email":
        query = query.order_by(asc(OrganizationInvitation.email))
    elif sort_by == "status":
        query = query.order_by(asc(OrganizationInvitation.status))
    else:
        query = query.order_by(desc(OrganizationInvitation.created_at))

    # Offset pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    res = await db.execute(query)
    invitations = res.scalars().all()

    # Pre-fetch organization names
    org_ids = list({inv.organization_id for inv in invitations if inv.organization_id})
    org_map = {}
    if org_ids:
        orgs_res = await db.execute(select(Organization).where(Organization.id.in_(org_ids)))
        org_map = {o.id: o.name for o in orgs_res.scalars().all()}

    items = [
        _build_invitation_response(
            inv, org_map.get(inv.organization_id) if inv.organization_id else None
        )
        for inv in invitations
    ]

    return InvitationListResponse(total=total, invitations=items)
