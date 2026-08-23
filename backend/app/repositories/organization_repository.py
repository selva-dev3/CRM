from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    Organization,
    OrganizationSetting,
    OrganizationSubscription,
    ProcessedWebhookEvent,
    SubscriptionPlan,
    User,
)


class OrganizationRepository:
    """DB query layer for the Organization entity. No business logic here."""

    async def get_by_id(self, db: AsyncSession, org_id: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalars().first()

    async def get_first(self, db: AsyncSession) -> Optional[Organization]:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        return result.scalars().first()

    async def list_all(self, db: AsyncSession) -> list[Organization]:
        result = await db.execute(select(Organization))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Organization:
        org = Organization(**data)
        db.add(org)
        return org

    async def delete(self, db: AsyncSession, org: Organization) -> None:
        await db.delete(org)

    async def create_default(self, db: AsyncSession) -> Organization:
        org = Organization(
            id="org-1",
            name="Default Organization",
            slug="default-org",
            status="active",
        )
        db.add(org)
        await db.commit()
        return org

    async def get_or_create_default(self, db: AsyncSession) -> Organization:
        org = Organization(
            id="org-1",
            name="Default Enterprise Organization",
            slug="default-enterprise",
            email="info@enterprise.com",
            phone="+91 9876543210",
            website="https://enterprise.com",
            industry="Information Technology",
            company_size="51-200",
            country="India",
            state="Tamil Nadu",
            city="Thoothukudi",
            address="123 Main Road",
            postal_code="628001",
            timezone="Asia/Kolkata",
            currency="INR",
            language="en",
            logo_url="",
            tax_number="GSTIN123456789",
            registration_number="CIN123456789",
            status="active",
            domain="enterprise.crm.com",
            plan="Enterprise",
            max_users=100,
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org

    async def count_members(self, db: AsyncSession, org_id: str) -> int:
        result = await db.execute(
            select(func.count(User.id)).where(User.organization_id == org_id)
        )
        count = result.scalar() or 0
        return max(count, 1)

    async def list_members(self, db: AsyncSession, org_id: str) -> list[User]:
        result = await db.execute(select(User).where(User.organization_id == org_id))
        return list(result.scalars().all())

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def delete_user(self, db: AsyncSession, user: User) -> None:
        await db.delete(user)

    async def get_setting(
        self, db: AsyncSession, org_id: str
    ) -> Optional[OrganizationSetting]:
        result = await db.execute(
            select(OrganizationSetting).where(OrganizationSetting.organization_id == org_id)
        )
        return result.scalars().first()

    async def create_setting(self, db: AsyncSession, *, data: dict) -> OrganizationSetting:
        setting = OrganizationSetting(**data)
        db.add(setting)
        return setting

    async def get_subscription(
        self, db: AsyncSession, org_id: str
    ) -> Optional[OrganizationSubscription]:
        result = await db.execute(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == org_id
            )
        )
        return result.scalars().first()

    get_subscription_by_org_id = get_subscription

    async def create_subscription(
        self, db: AsyncSession, *, data: dict
    ) -> OrganizationSubscription:
        sub = OrganizationSubscription(**data)
        db.add(sub)
        return sub

    async def get_plan_by_id(
        self, db: AsyncSession, plan_id: str
    ) -> Optional[SubscriptionPlan]:
        result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        return result.scalars().first()

    async def get_plan_by_slug(self, db: AsyncSession, slug: str) -> Optional[SubscriptionPlan]:
        result = await db.execute(
            select(SubscriptionPlan).where(func.lower(SubscriptionPlan.slug) == slug.lower())
        )
        return result.scalars().first()

    async def list_active_plans(self, db: AsyncSession) -> list[SubscriptionPlan]:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
        )
        return list(result.scalars().all())

    async def create_audit_log(
        self, db: AsyncSession, *, organization_id: str, action: str, details: str
    ) -> AuditLog:
        log = AuditLog(organization_id=organization_id, action=action, details=details)
        db.add(log)
        return log

    async def list_audit_logs(
        self, db: AsyncSession, org_id: str, *, limit: int = 20
    ) -> list[AuditLog]:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_subscription_by_checkout_session_id(
        self, db: AsyncSession, checkout_session_id: str
    ) -> Optional[OrganizationSubscription]:
        result = await db.execute(
            select(OrganizationSubscription).where(
                OrganizationSubscription.checkout_session_id == checkout_session_id
            )
        )
        return result.scalars().first()

    async def get_processed_webhook_event(
        self, db: AsyncSession, event_id: str
    ) -> Optional[ProcessedWebhookEvent]:
        result = await db.execute(
            select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event_id)
        )
        return result.scalars().first()

    async def record_processed_webhook_event(
        self, db: AsyncSession, *, event_id: str, event_type: str
    ) -> ProcessedWebhookEvent:
        event = ProcessedWebhookEvent(event_id=event_id, event_type=event_type)
        db.add(event)
        return event