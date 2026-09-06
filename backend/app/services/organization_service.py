import asyncio
import uuid
from typing import TypedDict

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Organization, OrganizationSubscription, SubscriptionPlan, User
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.crm_schemas import OrganizationUpdate
from app.services.s3_service import s3_service


class PlanInfo(TypedDict):
    name: str
    slug: str
    price_monthly: int
    max_users: int
    max_storage_gb: int
    ai_credits: int
    features: str


DEFAULT_PLANS: dict[str, PlanInfo] = {
    "free": {
        "name": "Free",
        "slug": "free",
        "price_monthly": 0,
        "max_users": 3,
        "max_storage_gb": 5,
        "ai_credits": 50,
        "features": "Dashboard, Leads, Contacts",
    },
    "starter": {
        "name": "Starter",
        "slug": "starter",
        "price_monthly": 999,
        "max_users": 10,
        "max_storage_gb": 20,
        "ai_credits": 500,
        "features": "Everything in Free, Deals, Tasks",
    },
    "professional": {
        "name": "Professional",
        "slug": "professional",
        "price_monthly": 2999,
        "max_users": 50,
        "max_storage_gb": 100,
        "ai_credits": 5000,
        "features": "Everything in Starter, AI, Reports",
    },
    "business": {
        "name": "Business",
        "slug": "business",
        "price_monthly": 6999,
        "max_users": 200,
        "max_storage_gb": 500,
        "ai_credits": 20000,
        "features": "Everything in Professional",
    },
    "enterprise": {
        "name": "Enterprise",
        "slug": "enterprise",
        "price_monthly": 29990,
        "max_users": 100,
        "max_storage_gb": 500,
        "ai_credits": 100000,
        "features": "Unlimited Everything, Priority Support",
    },
}


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
        "plan": getattr(org, "plan", "Enterprise") or "Enterprise",
        "max_users": getattr(org, "max_users", 100) or 100,
        "created_at": str(org.created_at) if getattr(org, "created_at", None) else "",
        "members_count": members_count,
    }


class OrganizationDomainService:
    """Business logic for the Organization domain (CRUD, subscription, branding)."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _require_current_org(self, db: AsyncSession, current_user: User) -> Organization:
        if not current_user.organization_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        org = await self.repository.get_by_id(db, current_user.organization_id)
        if not org:
            raise NotFoundError(message="Current organization not found")
        return org

    async def _require_requested_org(
        self, db: AsyncSession, *, org_id: str, current_user: User
    ) -> Organization:
        if current_user.organization_id != org_id:
            raise NotFoundError(message="Organization not found")
        return await self._require_current_org(db, current_user)

    async def get_or_create_default_org(
        self, db: AsyncSession, current_user: User | None = None
    ) -> Organization:
        if current_user and getattr(current_user, "organization_id", None):
            user_org = await self.repository.get_by_id(db, current_user.organization_id)
            if user_org:
                return user_org

        org = await self.repository.get_first(db)
        if not org:
            org = await self.repository.get_or_create_default(db)
        return org

    async def get_or_create_subscription(
        self, db: AsyncSession, org: Organization
    ) -> OrganizationSubscription:
        sub = await self.repository.get_subscription(db, org.id)
        if not sub:
            plan_slug = (org.plan or "enterprise").lower()
            db_plan = await self.repository.get_plan_by_slug(db, plan_slug)
            sub = await self.repository.create_subscription(
                db,
                data={
                    "id": str(uuid.uuid4()),
                    "organization_id": org.id,
                    "plan_id": db_plan.id if db_plan else None,
                    "status": "active",
                    "billing_cycle": "Monthly",
                    "amount": db_plan.price_monthly if db_plan else 29990.0,
                    "currency": "INR",
                    "auto_renew": True,
                },
            )
            await self._commit(db, "Failed to create subscription")
            await db.refresh(sub)
        return sub

    def _plan_to_info(
        self, db_plan: SubscriptionPlan | None, org: Organization | None = None
    ) -> dict:
        if db_plan:
            return {
                "name": db_plan.name,
                "slug": db_plan.slug,
                "price_monthly": db_plan.price_monthly,
                "max_users": db_plan.max_users,
                "max_storage_gb": db_plan.max_storage_gb,
                "ai_credits": db_plan.ai_credits,
                "features": db_plan.features or "",
            }
        plan_slug = org.plan.lower() if org and getattr(org, "plan", None) else "enterprise"
        return dict(DEFAULT_PLANS.get(plan_slug) or DEFAULT_PLANS["enterprise"])

    async def _resolve_plan_info(self, db: AsyncSession, org: Organization) -> dict:
        subscription = await self.get_or_create_subscription(db, org)
        db_plan = None
        if subscription.plan_id:
            db_plan = await self.repository.get_plan_by_id(db, subscription.plan_id)
        if not db_plan:
            plan_slug = (org.plan or "enterprise").lower()
            db_plan = await self.repository.get_plan_by_slug(db, plan_slug)
        return self._plan_to_info(db_plan, org)

    async def get_organization(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        members_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=members_count)

    async def get_current_organization(self, db: AsyncSession, current_user: User) -> dict:
        """Return only the organization assigned to the authenticated user."""
        org_id = current_user.organization_id
        if not org_id:
            raise ForbiddenError(message="Authenticated user has no current organization")

        org = await self.repository.get_by_id(db, org_id)
        if not org:
            raise NotFoundError(message="Current organization not found")

        members_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=members_count)

    async def list_members(self, db: AsyncSession, current_user: User) -> list[dict]:
        org = await self._require_current_org(db, current_user)
        users = await self.repository.list_members(db, org.id)
        if not users:
            raise NotFoundError(message="No members found in the organization")
        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role or "Sales Executive",
                "status": "Active" if u.is_active else "Inactive",
                "joined_at": str(u.created_at),
            }
            for u in users
        ]

    async def remove_member(self, db: AsyncSession, user_id: str, current_user: User) -> dict:
        if not current_user.organization_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        if user_id == current_user.id:
            raise APIException(
                message="You cannot remove your own organization membership",
                status_code=status.HTTP_409_CONFLICT,
            )
        user = await self.repository.get_user_by_id(
            db,
            user_id=user_id,
            organization_id=current_user.organization_id,
        )
        if user:
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
            "status": subscription.status or "active",
            "billing_cycle": subscription.billing_cycle or "Monthly",
            "amount": subscription.amount or plan_info["price_monthly"],
            "currency": subscription.currency or "INR",
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
        }

    async def list_subscription_plans(self, db: AsyncSession) -> list[dict]:
        db_plans = await self.repository.list_active_plans(db)
        if db_plans:
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "price_monthly": p.price_monthly,
                    "price_yearly": p.price_yearly,
                    "max_users": p.max_users,
                    "max_storage_gb": p.max_storage_gb,
                    "ai_credits": p.ai_credits,
                    "features": [f.strip() for f in p.features.split(",")] if p.features else [],
                    "is_active": p.is_active,
                }
                for p in db_plans
            ]

        return [
            {
                "id": f"plan-{info['slug']}",
                "name": info["name"],
                "slug": info["slug"],
                "price_monthly": info["price_monthly"],
                "price_yearly": info["price_monthly"] * 10,
                "max_users": info["max_users"],
                "max_storage_gb": info["max_storage_gb"],
                "ai_credits": info["ai_credits"],
                "features": [f.strip() for f in info["features"].split(",")],
                "is_active": True,
            }
            for info in DEFAULT_PLANS.values()
        ]

    async def upgrade_plan(self, db: AsyncSession, plan_slug: str) -> dict:
        """Never grant a paid plan through an unverified direct mutation."""
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Direct plan changes are disabled. Please use subscription checkout.",
        )

    async def cancel_subscription(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        subscription = await self.get_or_create_subscription(db, org)

        if subscription.subscription_id:
            from app.services.subscription_billing_service import SubscriptionBillingService

            return await SubscriptionBillingService(self.repository).set_auto_renew(
                db, current_user=current_user, auto_renew=False
            )

        subscription.auto_renew = False
        subscription.status = "cancelled"

        await self.repository.create_audit_log(
            db,
            organization_id=org.id,
            action="CANCEL_SUBSCRIPTION",
            details="Subscription cancelled.",
        )
        db.add(subscription)
        await self._commit(db, "Failed to cancel subscription")

        return {"message": "Subscription cancelled successfully", "status": "success"}

    async def resume_subscription(self, db: AsyncSession, current_user: User) -> dict:
        org = await self._require_current_org(db, current_user)
        subscription = await self.get_or_create_subscription(db, org)

        if subscription.subscription_id:
            from app.services.subscription_billing_service import SubscriptionBillingService

            return await SubscriptionBillingService(self.repository).set_auto_renew(
                db, current_user=current_user, auto_renew=True
            )

        subscription.auto_renew = True
        subscription.status = "active"

        await self.repository.create_audit_log(
            db,
            organization_id=org.id,
            action="RESUME_SUBSCRIPTION",
            details="Subscription resumed.",
        )
        db.add(subscription)
        await self._commit(db, "Failed to resume subscription")

        return {"message": "Subscription resumed successfully", "status": "success"}

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
            "ai_credits_used": 0,
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
                    "id": "dom-1",
                    "domain": org.domain,
                    "status": "verified",
                    "verified_at": str(org.updated_at or org.created_at),
                }
            ]
        return []

    async def get_organization_audit_logs(self, db: AsyncSession, current_user: User) -> list[dict]:
        org = await self._require_current_org(db, current_user)
        logs = await self.repository.list_audit_logs(db, org.id, limit=20)
        return [
            {
                "id": log.id,
                "action": log.action,
                "actor": log.user_id or "System Admin",
                "timestamp": str(log.created_at),
                "ip": log.ip_address or "127.0.0.1",
            }
            for log in logs
        ]

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
        user.role = "Admin"
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
        org = await self._require_requested_org(db, org_id=org_id, current_user=current_user)
        await self.repository.delete(db, org)
        await self._commit(db, "Failed to delete organization")
        return {
            "message": f"Organization '{org.name}' ({org_id}) deleted successfully",
            "status": "success",
        }


organization_domain_service = OrganizationDomainService()
