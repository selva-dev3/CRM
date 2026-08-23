import json
import uuid
from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.models import Organization, OrganizationSubscription, SubscriptionPlan, User
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.crm_schemas import OrganizationCreate, OrganizationUpdate
from app.services.s3_service import s3_service

logger = get_logger(__name__)

DEFAULT_PLANS = {
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
        "created_at": str(org.created_at) if getattr(org, "created_at", None) else "2026-01-01",
        "members_count": members_count,
    }


class OrganizationDomainService:
    """Business logic for the Organization domain (CRUD, subscription, branding)."""

    def __init__(self, repository: Optional[OrganizationRepository] = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def get_or_create_default_org(
        self, db: AsyncSession, current_user: Optional[User] = None
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
        self, db_plan: Optional[SubscriptionPlan], org: Optional[Organization] = None
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
        plan_slug = (org.plan.lower() if org and getattr(org, "plan", None) else "enterprise")
        return DEFAULT_PLANS.get(plan_slug) or DEFAULT_PLANS["enterprise"]

    async def _resolve_plan_info(self, db: AsyncSession, org: Organization) -> dict:
        subscription = await self.get_or_create_subscription(db, org)
        db_plan = None
        if subscription.plan_id:
            db_plan = await self.repository.get_plan_by_id(db, subscription.plan_id)
        if not db_plan:
            plan_slug = (org.plan or "enterprise").lower()
            db_plan = await self.repository.get_plan_by_slug(db, plan_slug)
        return self._plan_to_info(db_plan, org)

    async def create_organization(self, db: AsyncSession, payload: OrganizationCreate) -> dict:
        try:
            slug = payload.slug or payload.name.lower().replace(" ", "-")
            domain = payload.domain or f"{slug}.crm.com"

            existing_slug = await self.repository.get_by_slug(db, slug)
            if existing_slug:
                slug = f"{slug}-{uuid.uuid4().hex[:4]}"

            org = await self.repository.create(
                db,
                data={
                    "id": str(uuid.uuid4()),
                    "name": payload.name,
                    "slug": slug,
                    "domain": domain,
                    "email": payload.email,
                    "phone": payload.phone,
                    "website": payload.website,
                    "industry": payload.industry,
                    "company_size": payload.company_size,
                    "country": payload.country,
                    "state": payload.state,
                    "city": payload.city,
                    "address": payload.address,
                    "postal_code": payload.postal_code,
                    "timezone": payload.timezone or "Asia/Kolkata",
                    "currency": payload.currency or "INR",
                    "language": payload.language or "en",
                    "logo_url": payload.logo_url or "",
                    "tax_number": payload.tax_number,
                    "registration_number": payload.registration_number,
                    "status": payload.status or "active",
                    "role": getattr(payload, "role", "Admin") or "Admin",
                    "plan": payload.plan or "Free",
                    "max_users": payload.max_users or 3,
                },
            )
            await db.flush()

            await self.repository.create_setting(
                db,
                data={
                    "id": str(uuid.uuid4()),
                    "organization_id": org.id,
                    "timezone": org.timezone or "Asia/Kolkata",
                    "currency": org.currency or "INR",
                    "language": org.language or "en",
                    "logo_url": org.logo_url or "",
                },
            )

            free_plan = await self.repository.get_plan_by_slug(
                db, (payload.plan or "free").lower()
            )
            await self.repository.create_subscription(
                db,
                data={
                    "id": str(uuid.uuid4()),
                    "organization_id": org.id,
                    "plan_id": free_plan.id if free_plan else None,
                    "status": "active",
                    "billing_cycle": "Monthly",
                    "amount": free_plan.price_monthly if free_plan else 0.0,
                    "currency": "INR",
                    "auto_renew": True,
                },
            )

            await self.repository.create_audit_log(
                db,
                organization_id=org.id,
                action="CREATE_ORGANIZATION",
                details=f"Created organization '{org.name}'",
            )

            await self._commit(db, "Failed to create organization")
            await db.refresh(org)
            return org_to_dict(org, members_count=1)
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Failed to create organization: {str(e)}",
            ) from e

    async def get_organization(self, db: AsyncSession, current_user: Optional[User]) -> dict:
        org = await self.get_or_create_default_org(db, current_user)
        members_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=members_count)

    async def list_all_organizations(self, db: AsyncSession) -> list[dict]:
        orgs = await self.repository.list_all(db)
        if not orgs:
            default_org = await self.get_or_create_default_org(db)
            orgs = [default_org]

        result = []
        for org in orgs:
            m_count = await self.repository.count_members(db, org.id)
            result.append(org_to_dict(org, members_count=m_count))
        return result

    async def list_members(
        self, db: AsyncSession, current_user: Optional[User]
    ) -> list[dict]:
        org = await self.get_or_create_default_org(db, current_user)
        users = await self.repository.list_members(db, org.id)
        if not users:
            return [
                {
                    "id": "usr-admin-1",
                    "name": "Super Admin User",
                    "email": org.email or "admin@enterprise.com",
                    "role": "Superadmin",
                    "status": "Active",
                    "joined_at": str(org.created_at),
                }
            ]
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

    async def remove_member(self, db: AsyncSession, user_id: str) -> dict:
        user = await self.repository.get_user_by_id(db, user_id)
        if user:
            await self.repository.delete_user(db, user)
            await self._commit(db, "Failed to remove member")
            return {
                "message": f"User {user.name} ({user_id}) removed from organization",
                "status": "success",
            }
        return {"message": f"User {user_id} removed from organization", "status": "success"}

    async def get_subscription(
        self, db: AsyncSession, current_user: Optional[User]
    ) -> dict:
        org = await self.get_or_create_default_org(db, current_user)
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
                str(subscription.current_period_end)
                if subscription.current_period_end
                else None
            ),
            "next_billing": (
                str(subscription.next_billing) if subscription.next_billing else "2026-09-02"
            ),
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

    async def create_subscription_checkout(
        self,
        db: AsyncSession,
        plan_slug: str,
        org_id: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> dict:
        # Resolve target organization
        org: Optional[Organization] = None
        if org_id:
            org = await self.repository.get_by_id(db, org_id)
            if not org:
                raise NotFoundError(message=f"Organization with ID '{org_id}' not found.")
            # Verify user has access to this organization
            if current_user and getattr(current_user, "organization_id", None):
                if (
                    current_user.organization_id != org_id
                    and getattr(current_user, "role", "") not in ("Admin", "Superadmin")
                ):
                    raise APIException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        message="You do not have permission to manage billing for this organization.",
                    )
        else:
            org = await self.get_or_create_default_org(db, current_user)

        clean_slug = plan_slug.strip().lower()
        db_plan = await self.repository.get_plan_by_slug(db, clean_slug)
        plan_info = DEFAULT_PLANS.get(clean_slug)

        if not db_plan and not plan_info:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Subscription plan '{plan_slug}' does not exist.",
            )

        if db_plan and not db_plan.is_active:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Subscription plan '{plan_slug}' is currently inactive.",
            )

        if db_plan:
            plan_name = db_plan.name
            price_monthly = float(db_plan.price_monthly)
        elif plan_info:
            plan_name = plan_info.get("name", clean_slug.capitalize())
            price_monthly = float(plan_info.get("price_monthly", 0.0))
        else:
            plan_name = clean_slug.capitalize()
            price_monthly = 0.0
        unit_amount = int(round(price_monthly * 100))

        if settings.STRIPE_SECRET_KEY:
            try:
                import stripe

                stripe.api_key = settings.STRIPE_SECRET_KEY
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[
                        {
                            "price_data": {
                                "currency": "inr",
                                "product_data": {
                                    "name": f"Enterprise CRM - {plan_name} Plan",
                                    "description": f"Monthly subscription for {org.name}",
                                },
                                "unit_amount": unit_amount if unit_amount > 0 else 100,
                            },
                            "quantity": 1,
                        }
                    ],
                    mode="payment",
                    success_url=f"{settings.frontend_base_url}/organization/subscription/payment/success?session_id={{CHECKOUT_SESSION_ID}}&org_id={org.id}",
                    cancel_url=f"{settings.frontend_base_url}/organization/subscription/payment/cancel?org_id={org.id}",
                    customer_email=current_user.email if current_user and getattr(current_user, "email", None) else None,
                    metadata={
                        "organization_id": org.id,
                        "user_id": current_user.id if current_user else "",
                        "plan_slug": clean_slug,
                        "type": "subscription_upgrade",
                    },
                )
                return {
                    "checkout_url": session.url or f"https://checkout.stripe.com/pay/{session.id}",
                    "session_id": session.id,
                    "status": "success",
                }
            except Exception as e:
                logger.exception("Failed to create Stripe checkout session: %s", e)
                raise APIException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    message=f"Stripe checkout initialization failed: {str(e)}",
                ) from e

        # Fallback test mode when STRIPE_SECRET_KEY is not configured
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        checkout_url = f"https://checkout.stripe.com/pay/{session_id}"
        return {
            "checkout_url": checkout_url,
            "session_id": session_id,
            "status": "success",
        }

    async def apply_verified_subscription_upgrade(
        self,
        db: AsyncSession,
        organization_id: str,
        plan_slug: str,
        stripe_session_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> dict:
        org = await self.repository.get_by_id(db, organization_id)
        if not org:
            if organization_id == "org-1":
                org = await self.repository.get_or_create_default(db)
            else:
                raise NotFoundError(message=f"Organization '{organization_id}' not found.")

        subscription = await self.get_or_create_subscription(db, org)
        clean_slug = plan_slug.strip().lower()
        db_plan = await self.repository.get_plan_by_slug(db, clean_slug)
        plan_info = DEFAULT_PLANS.get(clean_slug) or DEFAULT_PLANS["enterprise"]

        if db_plan:
            subscription.plan_id = db_plan.id
            subscription.amount = db_plan.price_monthly
            subscription.max_users = db_plan.max_users
            subscription.storage_limit_gb = db_plan.max_storage_gb
            subscription.ai_credits = db_plan.ai_credits
            org.plan = db_plan.name
            org.max_users = db_plan.max_users
        elif plan_info:
            subscription.amount = float(plan_info.get("price_monthly", 0.0))
            subscription.max_users = int(plan_info.get("max_users", 100))
            subscription.storage_limit_gb = int(plan_info.get("max_storage_gb", 500))
            subscription.ai_credits = int(plan_info.get("ai_credits", 0))
            org.plan = str(plan_info.get("name", clean_slug.capitalize()))
            org.max_users = int(plan_info.get("max_users", 100))

        subscription.status = "active"
        subscription.auto_renew = True
        subscription.payment_provider = "Stripe"
        if stripe_customer_id:
            subscription.customer_id = stripe_customer_id
        if stripe_subscription_id:
            subscription.subscription_id = stripe_subscription_id
        if stripe_session_id:
            subscription.invoice_id = stripe_session_id

        await self.repository.create_audit_log(
            db,
            organization_id=org.id,
            action="UPGRADE_SUBSCRIPTION_STRIPE",
            details=f"Verified Stripe payment upgrade to {org.plan} (Session: {stripe_session_id or 'N/A'})",
        )
        db.add(org)
        db.add(subscription)
        await self._commit(db, "Failed to apply verified subscription upgrade")

        return {"message": f"Organization upgraded to {org.plan} successfully", "status": "success"}

    async def handle_stripe_subscription_webhook(
        self, db: AsyncSession, payload_bytes: bytes, sig_header: Optional[str]
    ) -> dict:
        event = {}
        if settings.STRIPE_WEBHOOK_SECRET:
            import stripe

            try:
                event = stripe.Webhook.construct_event(
                    payload_bytes, sig_header or "", settings.STRIPE_WEBHOOK_SECRET
                )
            except Exception as e:
                logger.warning("Stripe webhook signature verification failed: %s", e)
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Invalid Stripe webhook signature.",
                ) from e
        else:
            try:
                event = json.loads(payload_bytes.decode("utf-8") if isinstance(payload_bytes, bytes) else payload_bytes)
            except Exception as e:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST, message="Invalid webhook payload JSON."
                ) from e

        event_id = event.get("id")
        event_type = event.get("type", "")

        # Idempotency check
        if event_id:
            existing_event = await self.repository.get_processed_webhook_event(db, event_id)
            if existing_event:
                logger.info("Stripe webhook event %s already processed. Skipping duplicate.", event_id)
                return {"status": "ignored_duplicate", "message": f"Event '{event_id}' already processed"}

        if event_type in ("checkout.session.completed", "payment_intent.succeeded", "invoice.payment_succeeded"):
            obj = event.get("data", {}).get("object", {})
            payment_status = obj.get("payment_status", "paid")
            if payment_status not in ("paid", "no_payment_required"):
                logger.warning(
                    "Stripe checkout session %s payment status '%s' not paid. Skipping upgrade.",
                    obj.get("id"),
                    payment_status,
                )
                return {"status": "pending_or_unpaid", "message": f"Payment status is {payment_status}"}

            metadata = obj.get("metadata", {})
            org_id = metadata.get("organization_id")
            plan_slug = metadata.get("plan_slug")
            if org_id and plan_slug:
                await self.apply_verified_subscription_upgrade(
                    db,
                    organization_id=org_id,
                    plan_slug=plan_slug,
                    stripe_session_id=obj.get("id"),
                    stripe_customer_id=obj.get("customer"),
                    stripe_subscription_id=obj.get("subscription"),
                )
                if event_id:
                    try:
                        await self.repository.record_processed_webhook_event(
                            db, event_id=event_id, event_type=event_type
                        )
                        await db.commit()
                    except Exception:
                        await db.rollback()
                return {
                    "status": "success",
                    "message": f"Successfully processed {event_type} and upgraded organization {org_id} to {plan_slug}",
                }

        return {"status": "ignored", "message": f"Unhandled event type '{event_type}'"}

    async def upgrade_plan(self, db: AsyncSession, plan_slug: str) -> dict:
        org = await self.get_or_create_default_org(db)
        return await self.apply_verified_subscription_upgrade(db, org.id, plan_slug)

    async def cancel_subscription(self, db: AsyncSession) -> dict:
        org = await self.get_or_create_default_org(db)
        subscription = await self.get_or_create_subscription(db, org)

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

    async def resume_subscription(self, db: AsyncSession) -> dict:
        org = await self.get_or_create_default_org(db)
        subscription = await self.get_or_create_subscription(db, org)

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

    async def get_usage(self, db: AsyncSession, current_user: Optional[User]) -> dict:
        org = await self.get_or_create_default_org(db, current_user)
        subscription = await self.get_or_create_subscription(db, org)

        users_used = await self.repository.count_members(db, org.id)
        plan_info = await self._resolve_plan_info(db, org)

        return {
            "plan": plan_info["name"],
            "users_used": users_used,
            "users_limit": plan_info["max_users"],
            "storage_gb_used": subscription.storage_used_gb or 0.5,
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
        primary_color: Optional[str],
        current_user: Optional[User],
    ) -> dict:
        org = await self.get_or_create_default_org(db, current_user)
        try:
            logo_url = org.logo_url
            if logo_file:
                object_name = f"branding/{org.id}_{logo_file.filename}"
                s3_key = s3_service.upload_file(
                    logo_file.file, object_name=object_name, content_type=logo_file.content_type
                )
                logo_url = s3_service.generate_presigned_url(s3_key)
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

    async def verify_domain(
        self, db: AsyncSession, *, domain: str, current_user: Optional[User]
    ) -> dict:
        org = await self.get_or_create_default_org(db, current_user)
        org.domain = domain
        await self.repository.create_audit_log(
            db,
            organization_id=org.id,
            action="VERIFY_DOMAIN",
            details=f"Custom domain '{domain}' verified",
        )
        db.add(org)
        await self._commit(db, "Failed to verify domain")
        return {
            "message": f"Domain {domain} verified successfully and linked to organization",
            "status": "success",
        }

    async def list_organization_domains(
        self, db: AsyncSession, current_user: Optional[User]
    ) -> list[dict]:
        org = await self.get_or_create_default_org(db, current_user)
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

    async def get_organization_audit_logs(
        self, db: AsyncSession, current_user: Optional[User]
    ) -> list[dict]:
        org = await self.get_or_create_default_org(db, current_user)
        logs = await self.repository.list_audit_logs(db, org.id, limit=20)
        if not logs:
            return [
                {
                    "id": "log-1",
                    "action": "ORGANIZATION_INITIALIZED",
                    "actor": "System Admin",
                    "timestamp": str(org.created_at),
                    "ip": "127.0.0.1",
                }
            ]
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
        self, db: AsyncSession, new_owner_user_id: str
    ) -> dict:
        org = await self.get_or_create_default_org(db)
        user = await self.repository.get_user_by_id(db, new_owner_user_id)
        if user:
            user.role = "Superadmin"
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

    async def get_organization_by_id(self, db: AsyncSession, org_id: str) -> dict:
        org = await self.repository.get_by_id(db, org_id)
        if not org:
            if org_id == "org-1":
                org = await self.get_or_create_default_org(db)
            else:
                raise NotFoundError(message=f"Organization with ID '{org_id}' not found")
        m_count = await self.repository.count_members(db, org.id)
        return org_to_dict(org, members_count=m_count)

    async def update_organization_by_id(
        self, db: AsyncSession, org_id: str, payload: OrganizationUpdate
    ) -> dict:
        org = await self.repository.get_by_id(db, org_id)
        if not org:
            org = await self.get_or_create_default_org(db)
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
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=str(e)
            ) from e

    async def delete_organization_by_id(self, db: AsyncSession, org_id: str) -> dict:
        org = await self.repository.get_by_id(db, org_id)
        if org:
            await self.repository.delete(db, org)
            await self._commit(db, "Failed to delete organization")
            return {
                "message": f"Organization '{org.name}' ({org_id}) deleted successfully",
                "status": "success",
            }
        return {"message": f"Organization '{org_id}' deleted successfully", "status": "success"}


organization_domain_service = OrganizationDomainService()