from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Integration, IntegrationDelivery, User


class IntegrationRepository:
    """Query layer for the Integration domain — no business logic."""

    async def resolve_org_id(self, db: AsyncSession, current_user: User | None = None) -> str:
        if current_user and getattr(current_user, "organization_id", None):
            return current_user.organization_id
        raise ValueError("Authenticated organization context is required")

    async def list_all(
        self, db: AsyncSession, organization_id: str, limit: int = 20
    ) -> Sequence[Integration]:
        res = await db.execute(
            select(Integration)
            .where(Integration.organization_id == organization_id)
            .limit(limit)
        )
        return res.scalars().all()

    async def get_by_provider(
        self, db: AsyncSession, org_id: str, provider: str
    ) -> Integration | None:
        return await db.scalar(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.provider == provider,
            )
        )

    async def get_connected_by_provider(
        self, db: AsyncSession, org_id: str, provider: str
    ) -> Integration | None:
        return await db.scalar(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.provider == provider,
                Integration.is_connected == True,  # noqa: E712
            )
        )

    async def get_by_name_like(
        self, db: AsyncSession, organization_id: str, name: str
    ) -> Integration | None:
        res = await db.execute(
            select(Integration).where(
                Integration.organization_id == organization_id,
                Integration.name.ilike(f"%{name}%"),
            )
        )
        return res.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> Integration:
        integration = Integration(**data)
        db.add(integration)
        return integration

    async def queue_delivery(
        self, db: AsyncSession, *, data: dict
    ) -> IntegrationDelivery:
        delivery = IntegrationDelivery(**data)
        db.add(delivery)
        return delivery

    async def get_delivery_by_idempotency_key(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        integration_id: str,
        idempotency_key: str,
    ) -> IntegrationDelivery | None:
        return await db.scalar(
            select(IntegrationDelivery).where(
                IntegrationDelivery.organization_id == organization_id,
                IntegrationDelivery.integration_id == integration_id,
                IntegrationDelivery.idempotency_key == idempotency_key,
            )
        )

    async def commit(self, db: AsyncSession) -> None:
        await db.commit()
