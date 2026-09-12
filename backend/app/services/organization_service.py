import asyncio
import uuid

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id, ensure_tenant_managed_user
from app.models import Organization, OrganizationSubscription, SubscriptionPlan, User
from app.repositories.auth_repository import AuthRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import OrganizationUpdate
from app.services.organization_storage_service import lock_organization_storage
from app.services.s3_service import s3_service
from app.services.subscription_plan_service import FREE_PLAN_SLUG, free_subscription_data
from app.services.user_service import UserService


def org_to_dict(org: Organization, members_count: int = 1) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "slug": getattr(org, "slug", None) or "",
        "email": getattr(org, "email", None) or "",
        "phone": getattr(org, "phone", None) or "",
        "website": getattr(org, "website", None) or "",
        "industry": getattr(org, "industry", None) or "",
        "company_size": getattr(org, "company_size", None) or "",
        "country": getattr(org, "country", None) or "",
        "state": getattr(org, "state", None) or "",
        "city": getattr(org, "city", None) or "",
        "address": getattr(org, "address", None) or "",
        "postal_code": getattr(org, "postal_code", None) or "",
        "timezone": getattr(org, "timezone", "Asia/Kolkata") or "Asia/Kolkata",
        "currency": getattr(org, "currency", "INR") or "INR",
        "language": getattr(org, "language", "en") or "en",
        "logo_url": getattr(org, "logo_url", None) or "",
        "tax_number": getattr(org, "tax_number", None) or "",
        "registration_number": getattr(org, "registration_number", None) or "",
        "status": getattr(org, "status", "active") or "active",
        "role": getattr(org, "role", "Admin") or "Admin",
        "domain": getattr(org, "domain", "") or "",
        "plan": org.plan or "",
        "max_users": org.max_users,
        "created_at": str(org.created_at) if getattr(org, "created_at", None) else "",
        "members_count": members_count,
    }


class OrganizationDomainService:
    """Business logic for the Organization domain (CRUD, subscription, branding)."""

    def __init__(
        self,
        repository: OrganizationRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.repository = repository or OrganizationRepository()
        self.user_repository = user_repository or UserRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            if "uq_organizations_normalized_name" in str(e.orig):
                raise ConflictError(
                    message="An organization with this name already exists",
                    code="ORGANIZATION_NAME_CONFLICT",
                    fields={"name": "An organization with this name already exists"},
                ) from e
            raise ConflictError(message=error_message) from e
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _require_current_org(self, db: AsyncSession, current_user: User) -> Organization:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        org = await self.repository.get_by_id(db, organization_id)
        if not org:
            raise NotFoundError(message="Current organization not found")
        return org

    async def _require_requested_org(
        self, db: AsyncSession, *, org_id: str, current_user: User
    ) -> Organization:
        if getattr(current_user, "is_platform_admin", False) is True:
            org = await self.repository.get_by_id(db, org_id)
            if not org:
                raise NotFoundError(message="Organization not found")
            return org
        if effective_organization_id(current_user) != org_id:
            raise NotFoundError(message="Organization not found")
        return await self._require_current_org(db, current_user)

    async def list_platform_organizations(
        self, db: AsyncSession, current_user: User, *, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        if getattr(current_user, "is_platform_admin", False) is not True:
            raise ForbiddenError(message="Platform Super Admin access is required")
        return [
            org_to_dict(org, count)
            for org, count in await self.repository.list_with_member_counts(
                db, limit=limit, offset=offset
            )
        ]

    async def count_platform_organizations(self, db: AsyncSession, current_user: User) -> int:
        if getattr(current_user, "is_platform_admin", False) is not True:
            raise ForbiddenError(message="Platform Super Admin access is required")
        return await self.repository.count_organizations(db)

    async def get_or_create_default_org(
        self, db: AsyncSession, current_user: User | None = None
    ) -> Organization:
        if current_user:
            return await self._require_current_org(db, current_user)
        raise ForbiddenError(message="Authenticated organization context is required")

    async def get_or_create_subscription(
        self, db: AsyncSession, org: Organization
    ) -> OrganizationSubscription:
        sub = await self.repository.get_subscription(db, org.id)
        if not sub:
            locked_org = await self.repository.get_by_id_for_update(db, org.id)
            if not locked_org:
                raise NotFoundError(message="Organization not found")
            sub = await self.repository.get_subscription(db, org.id)
        if not sub:
            plan_slug = (org.plan or FREE_PLAN_SLUG).lower()
            if plan_slug != FREE_PLAN_SLUG:
                raise ConflictError(
                    message="The organization subscription requires administrator reconciliation",
                    code="SUBSCRIPTION_DATA_INTEGRITY_ERROR",
                )
            db_plan = await self.repository.get_plan_by_slug(db, FREE_PLAN_SLUG)
            if not db_plan or not db_plan.is_active or db_plan.price_monthly != 0:
                raise APIException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    code="FREE_SUBSCRIPTION_PLAN_UNAVAILABLE",
                    message="The default subscription plan is not configured",
                )
            sub = await self.repository.create_subscription(
                db,
                data=free_subscription_data(organization_id=org.id, plan=db_plan, current_users=1),
            )
            org.plan = db_plan.name
            org.max_users = db_plan.max_users
            await self._commit(db, "Failed to create subscription")
            await db.refresh(sub)
        return sub

    def _plan_to_info(self, db_plan: SubscriptionPlan) -> dict:
        return {
            "name": db_plan.name,
            "slug": db_plan.slug,
            "price_monthly": db_plan.price_monthly,
            "max_users": db_plan.max_users,
            "max_storage_gb": db_plan.max_storage_gb,
            "ai_credits": db_plan.ai_credits,
            "features": db_plan.features or "",
        }

    async def _resolve_plan_info(self, db: AsyncSession, org: Organization) -> dict:
        subscription = await self.get_or_create_subscription(db, org)
        db_plan = None
        if subscription.plan_id:
            db_plan = await self.repository.get_plan_by_id(db, subscription.plan_id)
        if not db_plan:
            plan_slug = (org.plan or FREE_PLAN_SLUG).lower()
            db_plan = await self.repository.get_plan_by_slug(db, plan_slug)
        if not db_plan:
            raise ConflictError(
                message="The subscription plan record requires administrator reconciliation",
                code="SUBSCRIPTION_DATA_INTEGRITY_ERROR",
            )
        return self._plan_to_info(db_plan)

    async def get_organization(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        members_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=members_count)

    async def get_current_organization(self, db: AsyncSession, current_user: User) -> dict:
        """Return only the organization assigned to the authenticated user."""
        org_id = effective_organization_id(current_user)
        if not org_id:
            raise ForbiddenError(message="Authenticated user has no current organization")

        org = await self.repository.get_by_id(db, org_id)
        if not org:
            raise NotFoundError(message="Current organization not found")

        members_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=members_count)

    async def list_members(
        self, db: AsyncSession, current_user: User, *, page: int = 1, limit: int = 15
    ) -> list[dict]:
        org = await self._require_current_org(db, current_user)
        users = await self.repository.list_members(db, org.id, page=page, limit=limit)
        role_names = await self.user_repository.effective_role_names_for_users(
            db, list(users), org.id
        )
        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": role_names.get(u.id) or "User",
                "status": "Active" if u.is_active else "Inactive",
                "joined_at": str(u.created_at),
            }
            for u in users
        ]

    async def remove_member(self, db: AsyncSession, user_id: str, current_user: User) -> dict:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        if user_id == current_user.id:
            raise APIException(
                message="You cannot remove your own organization membership",
                status_code=status.HTTP_409_CONFLICT,
            )
        user = await self.repository.get_user_by_id(
            db,
            user_id=user_id,
            organization_id=organization_id,
        )
        if user:
            ensure_tenant_managed_user(user)
            await UserService()._ensure_not_last_admin(db, user)
            await AuthRepository().revoke_all_user_sessions(db, user.id)
            await self.repository.delete_user(db, user)
            await self._commit(db, "Failed to remove member")
            return {
                "message": f"User {user.name} ({user_id}) removed from organization",
                "status": "success",
            }
        raise NotFoundError(message="User not found in the organization")

    async def get_subscription(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        subscription = await self.get_or_create_subscription(db, org)
        plan_info = await self._resolve_plan_info(db, org)

        return {
            "plan": plan_info["name"],
            "plan_slug": plan_info["slug"],
            "provider_linked": bool(subscription.subscription_id and subscription.customer_id),
            "status": subscription.status or "active",
            "billing_cycle": subscription.billing_cycle,
            "amount": subscription.amount,
            "currency": subscription.currency,
            "trial": subscription.trial or False,
            "auto_renew": (
                subscription.auto_renew if subscription.auto_renew is not None else True
            ),
            "current_period_start": (
                str(subscription.current_period_start)
                if subscription.current_period_start
                else None
            ),
            "current_period_end": (
                str(subscription.current_period_end) if subscription.current_period_end else None
            ),
            "next_billing": (str(subscription.next_billing) if subscription.next_billing else None),
            "max_users": plan_info["max_users"],
            "storage_limit_gb": plan_info["max_storage_gb"],
            "ai_credits": plan_info["ai_credits"],
            "features": plan_info["features"],
            "reconciliation_required": bool(
                getattr(subscription, "reconciliation_required", False)
            ),
            "last_provider_error_code": getattr(subscription, "last_provider_error_code", None),
        }

    async def list_subscription_plans(self, db: AsyncSession) -> list[dict]:
        db_plans = await self.repository.list_plans(db)
        return [
            {
                "id": plan.id,
                "name": plan.name,
                "slug": plan.slug,
                "description": plan.description,
                "price_monthly": plan.price_monthly,
                "price_yearly": plan.price_yearly,
                "currency": plan.currency,
                "billing_cycle": plan.billing_cycle,
                "max_users": plan.max_users,
                "max_storage_gb": plan.max_storage_gb,
                "ai_credits": plan.ai_credits,
                "features": [f.strip() for f in plan.features.split(",")] if plan.features else [],
                "is_popular": plan.is_popular,
                "is_active": plan.is_active,
                "sort_order": plan.sort_order,
            }
            for plan in db_plans
        ]

    async def upgrade_plan(self, db: AsyncSession, plan_slug: str) -> dict:
        """Never grant a paid plan through an unverified direct mutation."""
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Direct plan changes are disabled. Please use subscription checkout.",
        )

    async def cancel_subscription(self, db: AsyncSession, current_user: User) -> dict:
        from app.services.subscription_billing_service import SubscriptionBillingService

        return await SubscriptionBillingService(self.repository).set_auto_renew(
            db, current_user=current_user, auto_renew=False
        )

    async def resume_subscription(self, db: AsyncSession, current_user: User) -> dict:
        from app.services.subscription_billing_service import SubscriptionBillingService

        return await SubscriptionBillingService(self.repository).set_auto_renew(
            db, current_user=current_user, auto_renew=True
        )

    async def get_usage(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        subscription = await self.get_or_create_subscription(db, org)

        users_used = await self.repository.count_members(db, org.id)
        plan_info = await self._resolve_plan_info(db, org)

        return {
            "plan": plan_info["name"],
            "users_used": users_used,
            "users_limit": plan_info["max_users"],
            "storage_gb_used": subscription.storage_used_gb or 0,
            "storage_gb_limit": plan_info["max_storage_gb"],
            "ai_credits_limit": plan_info["ai_credits"],
            "billing_status": subscription.status or "active",
        }

    async def update_branding(
        self,
        db: AsyncSession,
        *,
        logo_file,
        primary_color: str | None,
        current_user: User,
    ) -> dict:
        org = await self._require_current_org(db, current_user)
        await lock_organization_storage(db, org.id)
        try:
            logo_url = org.logo_url
            if logo_file:
                object_name = f"branding/{org.id}_{logo_file.filename}"
                s3_key = await asyncio.to_thread(
                    s3_service.upload_file,
                    logo_file.file,
                    object_name=object_name,
                    content_type=logo_file.content_type,
                )
                logo_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
                org.logo_url = logo_url

            setting = await self.repository.get_setting(db, org.id)
            if not setting:
                await self.repository.create_setting(
                    db,
                    data={
                        "id": str(uuid.uuid4()),
                        "organization_id": org.id,
                        "primary_color": primary_color or "#3B82F6",
                        "logo_url": logo_url or "",
                    },
                )
            else:
                if primary_color:
                    setting.primary_color = primary_color
                if logo_url:
                    setting.logo_url = logo_url

            db.add(org)
            await self._commit(db, "Failed to update branding")
            return {
                "message": "Organization branding and logo updated on S3 and saved to DB",
                "status": "success",
            }
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Branding S3 upload failed: {str(e)}",
            ) from e

    async def verify_domain(self, db: AsyncSession, *, domain: str, current_user: User) -> dict:
        raise APIException(
            message="Custom domain DNS verification is not configured",
            code="DOMAIN_VERIFICATION_UNAVAILABLE",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )

    async def list_organization_domains(self, db: AsyncSession, current_user: User) -> list[dict]:
        org = await self._require_current_org(db, current_user)
        if org.domain:
            return [
                {
                    "id": f"domain:{org.id}",
                    "domain": org.domain,
                    "status": "pending",
                    "verified_at": None,
                }
            ]
        return []

    async def get_organization_audit_logs(
        self, db: AsyncSession, current_user: User, *, page: int = 1, limit: int = 20
    ) -> list[dict]:
        org = await self._require_current_org(db, current_user)
        logs = await self.repository.list_audit_logs(db, org.id, page=page, limit=limit)
        return [
            {
                "id": log.id,
                "action": log.action,
                "actor": log.user_id or "Unknown",
                "timestamp": str(log.created_at),
                "ip": log.ip_address,
            }
            for log in logs
        ]

    async def count_organization_audit_logs(self, db: AsyncSession, current_user: User) -> int:
        org = await self._require_current_org(db, current_user)
        return await self.repository.count_audit_logs(db, org.id)

    async def transfer_organization_ownership(
        self, db: AsyncSession, new_owner_user_id: str, current_user: User
    ) -> dict:
        org = await self._require_current_org(db, current_user)
        user = await self.repository.get_user_by_id(
            db,
            user_id=new_owner_user_id,
            organization_id=org.id,
        )
        if not user:
            raise NotFoundError(message="New owner was not found in the organization")
        ensure_tenant_managed_user(user)
        from app.repositories.role_repository import RoleRepository

        role_repository = RoleRepository()
        admin_role = await role_repository.get_role_by_id_or_name(
            db, "Admin", organization_id=org.id
        )
        if not admin_role or admin_role.organization_id != org.id:
            raise ConflictError(
                message="The organization Admin role is not provisioned",
                code="ADMIN_ROLE_NOT_CONFIGURED",
            )
        user.role = admin_role.id
        await role_repository.replace_user_role(db, user.id, admin_role.id)
        db.add(user)
        await self.repository.create_audit_log(
            db,
            organization_id=org.id,
            action="TRANSFER_OWNERSHIP",
            details=f"Ownership transferred to user ID '{new_owner_user_id}'",
        )
        await self._commit(db, "Failed to transfer ownership")
        return {
            "message": f"Organization ownership transferred to user {new_owner_user_id}",
            "status": "success",
        }

    async def get_organization_by_id(
        self, db: AsyncSession, org_id: str, current_user: User
    ) -> dict:
        org = await self._require_requested_org(db, org_id=org_id, current_user=current_user)
        m_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=m_count)

    async def update_organization_by_id(
        self,
        db: AsyncSession,
        org_id: str,
        payload: OrganizationUpdate,
        current_user: User,
    ) -> dict:
        org = await self._require_requested_org(db, org_id=org_id, current_user=current_user)
        updates = payload.model_dump(exclude_unset=True)
        if any(
            updates.get(field) is not None and updates[field] != getattr(org, field)
            for field in ("plan", "max_users")
        ):
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Plan and entitlement changes require verified subscription billing.",
            )
        try:
            for field, value in payload.model_dump(exclude_unset=True).items():
                if value is not None and hasattr(org, field):
                    setattr(org, field, value)

            await self.repository.create_audit_log(
                db,
                organization_id=org.id,
                action="UPDATE_ORGANIZATION",
                details=f"Updated organization '{org.name}' settings",
            )

            await self._commit(db, "Failed to update organization")
            await db.refresh(org)
            m_count = await self.repository.count_members(db, org.id)
            return org_to_dict(org, members_count=m_count)
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to update organization",
            ) from e

    async def delete_organization_by_id(
        self, db: AsyncSession, org_id: str, current_user: User
    ) -> dict:
        from app.services.organization_lifecycle_service import organization_lifecycle_service

        return await organization_lifecycle_service.delete(db, org_id, current_user)


organization_domain_service = OrganizationDomainService()
