import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.core.permissions import (
    effective_organization_id,
    ensure_can_assign_role,
    is_super_admin_role,
    is_super_admin_user,
)
from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    Organization,
    OrganizationInvitation,
    OrganizationSubscription,
    Role,
    SubscriptionPlan,
    User,
)
from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
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
from app.services.subscription_plan_service import (
    FREE_PLAN_SLUG,
    apply_plan_to_organization,
    build_free_subscription,
)

logger = get_logger(__name__)


async def _require_free_plan(db: AsyncSession) -> SubscriptionPlan:
    plan = await db.scalar(
        select(SubscriptionPlan).where(
            func.lower(SubscriptionPlan.slug) == FREE_PLAN_SLUG,
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.price_monthly == 0,
        )
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The default subscription plan is not configured",
        )
    return plan


def _require_current_organization_id(current_user: User) -> str:
    organization_id = effective_organization_id(current_user)
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user has no current organization",
        )
    return organization_id


def _build_invitation_response(
    inv: OrganizationInvitation, org_name: str | None = None, role_name: str | None = None
) -> InvitationResponse:
    invite_url = f"{settings.frontend_base_url}/accept-invite/organization/{inv.token}"
    expires_str = inv.expires_at.isoformat() if inv.expires_at else ""
    accepted_str = inv.accepted_at.isoformat() if inv.accepted_at else None
    created_str = inv.created_at.isoformat() if inv.created_at else ""

    return InvitationResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        organization_name=org_name,
        email=inv.email,
        full_name=inv.full_name,
        role=role_name or inv.role_id or "Admin",
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
    2. Prefer the target organization role, including when a legacy global ID
       names its equivalent. Legacy organizations without a scoped equivalent
       retain their existing global-role compatibility.
    3. The super_admin role may only be assigned by a super_admin actor (403 otherwise).
    """
    role_str = (role_value or "").strip() or "Admin"
    repository = OrganizationLifecycleRepository()
    role = await repository.resolve_invitation_role(db, role_str, target_organization_id)
    if not role and role_str.lower() == "administrator":
        role = await repository.resolve_invitation_role(db, "Admin", target_organization_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: '{role_value}'",
        )
    if role.organization_id != target_organization_id:
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
    from app.core.errors import ForbiddenError
    from app.schemas.organization_lifecycle import (
        InitialAdminInvitation,
        PlatformOrganizationCreate,
    )
    from app.services.organization_lifecycle_service import organization_lifecycle_service

    if payload.role_id not in (None, "Admin"):
        raise ForbiddenError(
            message="A new organization's initial invitation must use its Admin role"
        )
    created = await organization_lifecycle_service.create(
        db,
        PlatformOrganizationCreate(
            name=f"{payload.full_name.strip()}'s Organization",
            initial_admin=InitialAdminInvitation(name=payload.full_name, email=payload.email),
        ),
        current_user,
    )
    if not created.invitation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization was created without its required administrator invitation",
        )
    invitation = await db.get(OrganizationInvitation, created.invitation.id)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Administrator invitation could not be loaded",
        )
    return NewOrganizationInviteResponse(
        organization=created.organization.model_dump(),
        invitation=_build_invitation_response(invitation, created.organization.name, "Admin"),
        message=(
            "Organization created and invitation sent"
            if created.invitation.delivery_status == "sent"
            else "Organization created; invitation email failed. Open the organization to resend it."
        ),
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
    target_org_id = effective_organization_id(current_user)
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
    # Serialize all invitation creation paths for this normalized email.
    lifecycle_repository = OrganizationLifecycleRepository()
    email_clean = payload.email.strip().lower()
    await lifecycle_repository.lock_invitation_email(db, email_clean)
    org = await lifecycle_repository.lock_invitation_organization(db, target_org_id)
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

    # Resolve and authorize the role only after locking and revalidating the tenant.
    role = await _resolve_invitation_role(
        db,
        current_user,
        payload.role or "Admin",
        target_organization_id=target_org_id,
    )
    role_name = role.name

    if await lifecycle_repository.pending_invitation_in_other_organization(
        db, email_clean, target_org_id
    ) or await lifecycle_repository.pending_legacy_invitation_exists(db, email_clean):
        raise ConflictError(message="This email already has a pending invitation")
    existing_inv = await lifecycle_repository.pending_invitation_for_organization(
        db, email_clean, target_org_id
    )
    if await lifecycle_repository.email_in_use(db, email_clean):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already has an account.",
        )

    token = f"inv_{uuid.uuid4().hex}"
    expires_at = datetime.now(UTC) + timedelta(hours=24)

    if existing_inv:
        existing_inv.token = token
        existing_inv.expires_at = expires_at
        existing_inv.role_id = role.id
        existing_inv.full_name = payload.full_name or existing_inv.full_name
        existing_inv.organization_id = target_org_id
        invitation = existing_inv
    else:
        invitation = OrganizationInvitation(
            id=str(uuid.uuid4()),
            organization_id=target_org_id,
            email=email_clean,
            full_name=payload.full_name.strip() if payload.full_name else None,
            role_id=role.id,
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
    invite_url = f"{settings.frontend_base_url}/accept-invite/organization/{token}"
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
        await db.execute(
            update(OrganizationInvitation)
            .where(
                OrganizationInvitation.id == inv.id,
                OrganizationInvitation.token == token.strip(),
                OrganizationInvitation.status == "Pending",
                OrganizationInvitation.expires_at == inv.expires_at,
            )
            .values(status="Expired")
            .execution_options(synchronize_session=False)
        )
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

    names = await OrganizationLifecycleRepository().role_names(
        db, [inv.role_id] if inv.role_id else []
    )
    return InvitationStatusResponse(
        organization=org_dict,
        email=inv.email,
        full_name=inv.full_name,
        role=(names.get(inv.role_id, inv.role_id) if inv.role_id else None) or "Admin",
        expires_at=inv_expires.isoformat(),
        status=inv.status,
        is_valid=True,
    )


async def accept_organization_invitation(
    db: AsyncSession, token: str, payload: AcceptInvitationRequest
) -> dict:
    try:
        return await _accept_organization_invitation(db, token, payload)
    except IntegrityError as exc:
        try:
            await db.rollback()
        except SQLAlchemyError:
            logger.error("Invitation acceptance rollback failed")
        raise ConflictError(
            message="Invitation acceptance conflicts with an existing account or organization",
            code="INVITATION_ACCEPTANCE_CONFLICT",
        ) from exc
    except Exception:
        try:
            await db.rollback()
        except SQLAlchemyError:
            logger.error("Invitation acceptance rollback failed")
        raise


async def _accept_organization_invitation(
    db: AsyncSession, token: str, payload: AcceptInvitationRequest
) -> dict:
    """Join an existing organization using its invitation and scoped role."""
    inv = await OrganizationLifecycleRepository().lock_invitation_for_acceptance(db, token.strip())
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    await get_and_validate_invitation_by_token(db, token)

    email_clean = inv.email.strip().lower()
    full_name = payload.full_name or inv.full_name or email_clean.split("@")[0].capitalize()

    # 2. Resolve the existing organization; acceptance never provisions a tenant.
    org = None
    if inv.organization_id:
        org = await db.scalar(select(Organization).where(Organization.id == inv.organization_id))

    if not org or not org.is_active or org.status != "active":
        raise HTTPException(
            status_code=409,
            detail="This invitation has no active organization. Contact the platform administrator.",
        )

    existing_subscription = await db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.organization_id == org.id)
    )
    if not existing_subscription:
        if (org.plan or "").lower() != FREE_PLAN_SLUG:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The organization subscription requires administrator reconciliation",
            )
        free_plan = await _require_free_plan(db)
        apply_plan_to_organization(org, free_plan)
        existing_subscription = build_free_subscription(
            organization_id=org.id, plan=free_plan, current_users=0
        )
        db.add(existing_subscription)
        await db.flush()
        inv.subscription_id = existing_subscription.id

    member_count = await OrganizationLifecycleRepository().tenant_member_count(db, org.id)
    if member_count >= org.max_users:
        raise ConflictError(
            message="The organization has reached its member limit",
            code="ORGANIZATION_MEMBER_LIMIT",
        )

    # Existing accounts are never moved or have credentials replaced by onboarding.
    from app.repositories.auth_repository import AuthRepository

    user = await db.scalar(select(User).where(func.lower(User.email) == email_clean))
    if user:
        raise ConflictError(
            message="This email already belongs to an account. Contact the platform administrator."
        )
    invited_role = await OrganizationLifecycleRepository().resolve_invitation_role(
        db, inv.role_id or "Admin", org.id
    )
    if not invited_role or is_super_admin_role(invited_role):
        raise HTTPException(
            status_code=400, detail="Invitation role is not valid for organization membership"
        )
    user = User(
        id=str(uuid.uuid4()),
        name=full_name,
        email=email_clean,
        hashed_password=get_password_hash(payload.password),
        role=invited_role.id,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await AuthRepository().assign_user_role(db, user_id=user.id, role_id=invited_role.id)
    await db.flush()

    from app.services.auth_service import AuthService

    user_permissions = await AuthService().get_user_permissions(
        db, user, resolved_role_name=invited_role.name
    )

    existing_subscription.current_users = member_count + 1

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
        details=f"Invitation accepted by '{user.email}' for organization '{org.name}' ({org.id}).",
    )
    db.add(audit)

    # 6. Stage a hardened access/refresh family in this acceptance transaction.
    access_token, refresh_token = await AuthService().issue_session_tokens(db, user.id)
    await db.commit()
    await db.refresh(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": invited_role.name,
            "organization_id": user.organization_id,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_platform_admin": False,
            "permissions": user_permissions,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "domain": org.domain,
            "plan": org.plan,
        },
        "message": f"Invitation accepted! Your account is active in organization '{org.name}'.",
    }


async def resend_organization_invitation(
    db: AsyncSession, invitation_id: str, current_user: User
) -> InvitationResponse:
    """Generate new token, expire old token, send email again."""
    organization_id = _require_current_organization_id(current_user)
    inv = await OrganizationLifecycleRepository().lock_invitation_for_management(
        db, invitation_id, organization_id
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
        plan_name=org.plan if org and org.plan else "Free",
        token=new_token,
        expires_at_str="24 Hours",
    )

    names = await OrganizationLifecycleRepository().role_names(
        db, [inv.role_id] if inv.role_id else []
    )
    return _build_invitation_response(
        inv,
        org.name if org else None,
        names.get(inv.role_id) if inv.role_id else None,
    )


async def cancel_organization_invitation(
    db: AsyncSession, invitation_id: str, current_user: User
) -> dict:
    """Cancel an invitation."""
    organization_id = _require_current_organization_id(current_user)
    inv = await OrganizationLifecycleRepository().lock_invitation_for_management(
        db, invitation_id, organization_id
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

    role_names = await OrganizationLifecycleRepository().role_names(
        db, [inv.role_id for inv in invitations if inv.role_id]
    )
    items = [
        _build_invitation_response(
            inv,
            org_map.get(inv.organization_id) if inv.organization_id else None,
            role_names.get(inv.role_id) if inv.role_id else None,
        )
        for inv in invitations
    ]

    return InvitationListResponse(total=total, invitations=items)
