from __future__ import annotations

import builtins
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models import Company, Contact, User
from app.models.deal import Deal, DealActivity, DealProduct, DealStage, DealStageHistory
from app.models.product import Product


class DealRepository:
    """DB query layer for the Deal domain. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        stage: str | None = None,
        access=None,
    ) -> builtins.list[Deal]:
        stmt = select(Deal).where(Deal.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if search and search.strip():
            stmt = stmt.where(Deal.title.ilike(f"%{search.strip()}%"))
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        stmt = (
            stmt.order_by(Deal.created_at.desc(), Deal.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        stage: str | None = None,
        access=None,
    ) -> int:
        stmt = select(func.count()).select_from(Deal).where(Deal.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if search and search.strip():
            stmt = stmt.where(Deal.title.ilike(f"%{search.strip()}%"))
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def list_all(
        self, db: AsyncSession, *, organization_id: str, access=None
    ) -> builtins.list[Deal]:
        stmt = select(Deal).where(Deal.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        result = await db.execute(stmt.order_by(Deal.created_at.desc()))
        return list(result.scalars().all())

    async def list_by_contact(
        self,
        db: AsyncSession,
        *,
        contact_id: str,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
        access=None,
    ) -> builtins.list[Deal]:
        stmt = (
            select(Deal)
            .where(
                Deal.contact_id == contact_id,
                Deal.organization_id == organization_id,
            )
            .order_by(Deal.created_at.desc(), Deal.id.desc())
        )
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_contact(
        self, db: AsyncSession, *, contact_id: str, organization_id: str, access=None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Deal)
            .where(
                Deal.contact_id == contact_id,
                Deal.organization_id == organization_id,
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        return int((await db.execute(stmt)).scalar_one())

    async def list_activities_by_contact(
        self,
        db: AsyncSession,
        *,
        contact_id: str,
        organization_id: str,
        limit: int | None = None,
    ) -> builtins.list[DealActivity]:
        stmt = (
            select(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(
                Deal.contact_id == contact_id,
                Deal.organization_id == organization_id,
            )
            .order_by(DealActivity.timestamp.desc(), DealActivity.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_activities_by_contact(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(
                Deal.contact_id == contact_id,
                Deal.organization_id == organization_id,
            )
        )
        return int((await db.execute(stmt)).scalar_one())

    async def list_by_company(
        self,
        db: AsyncSession,
        *,
        company_id: str,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
        access=None,
    ) -> builtins.list[Deal]:
        stmt = (
            select(Deal)
            .where(
                Deal.company_id == company_id,
                Deal.organization_id == organization_id,
            )
            .order_by(Deal.created_at.desc(), Deal.id.desc())
        )
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_company(
        self, db: AsyncSession, *, company_id: str, organization_id: str, access=None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Deal)
            .where(
                Deal.company_id == company_id,
                Deal.organization_id == organization_id,
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        return int((await db.execute(stmt)).scalar_one())

    async def get_by_id_scoped(
        self,
        db: AsyncSession,
        *,
        deal_id: str,
        organization_id: str,
        lock: bool = False,
        access=None,
    ) -> Deal | None:
        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.organization_id == organization_id,
        )
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def set_won(self, db: AsyncSession, deal: Deal, amount: float) -> None:
        deal.stage = "Closed Won"
        deal.probability = 100
        deal.amount = amount

    async def create_initial_stage_history(
        self, db: AsyncSession, *, deal: Deal, actor_id: str | None
    ) -> DealStageHistory:
        history = DealStageHistory(
            organization_id=deal.organization_id,
            deal_id=deal.id,
            stage=deal.stage,
            actor_id=actor_id,
        )
        db.add(history)
        return history

    async def transition_stage(
        self,
        db: AsyncSession,
        *,
        deal: Deal,
        stage: str,
        actor_id: str | None,
    ) -> bool:
        """Record a stage transition and update its reporting timestamps atomically."""
        if deal.stage == stage:
            return False

        now = datetime.now(UTC)
        current_result = await db.execute(
            select(DealStageHistory)
            .where(
                DealStageHistory.deal_id == deal.id,
                DealStageHistory.organization_id == deal.organization_id,
                DealStageHistory.exited_at.is_(None),
            )
            .with_for_update()
        )
        current = current_result.scalar_one_or_none()
        if current:
            current.exited_at = now

        db.add(
            DealStageHistory(
                organization_id=deal.organization_id,
                deal_id=deal.id,
                stage=stage,
                entered_at=now,
                actor_id=actor_id,
            )
        )
        deal.stage = stage
        deal.closed_at = now if stage in {"Closed Won", "Closed Lost"} else None
        return True

    async def add_activity(
        self, db: AsyncSession, *, deal_id: str, action: str, actor_id: str | None
    ) -> DealActivity:
        activity = DealActivity(deal_id=deal_id, action=action, performed_by=actor_id)
        db.add(activity)
        return activity

    async def list_activities(
        self,
        db: AsyncSession,
        *,
        deal_id: str,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
    ) -> builtins.list[DealActivity]:
        stmt = (
            select(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(
                DealActivity.deal_id == deal_id,
                Deal.organization_id == organization_id,
            )
            .order_by(DealActivity.timestamp.desc(), DealActivity.id.desc())
        )
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_activities(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(DealActivity.deal_id == deal_id, Deal.organization_id == organization_id)
        )
        return int(result.scalar_one())

    async def get_sales_customer(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        company_id: str | None,
        contact_id: str | None,
    ):
        company = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
            )
        )
        contact = await db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.organization_id == organization_id,
            )
        )
        return company.scalar_one_or_none(), contact.scalar_one_or_none()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str], *, organization_id: str, access=None
    ) -> builtins.list[Deal]:
        stmt = select(Deal).where(Deal.id.in_(ids), Deal.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Deal.assigned_to, created_column=Deal.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Deal:
        deal = Deal(**data)
        db.add(deal)
        return deal

    async def delete(self, db: AsyncSession, deal: Deal) -> None:
        await db.delete(deal)

    async def user_exists(self, db: AsyncSession, user_id: str, *, organization_id: str) -> bool:
        result = await db.execute(
            select(User.id)
            .where(User.id == user_id, User.organization_id == organization_id)
            .limit(1)
        )
        return result.scalars().first() is not None

    async def first_user_id(self, db: AsyncSession, *, organization_id: str) -> str | None:
        result = await db.execute(
            select(User.id).where(User.organization_id == organization_id).limit(1)
        )
        return result.scalars().first()

    async def company_exists(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> bool:
        result = await db.execute(
            select(Company.id)
            .where(Company.id == company_id, Company.organization_id == organization_id)
            .limit(1)
        )
        return result.scalars().first() is not None

    async def contact_exists(
        self, db: AsyncSession, contact_id: str, *, organization_id: str
    ) -> bool:
        result = await db.execute(
            select(Contact.id)
            .where(Contact.id == contact_id, Contact.organization_id == organization_id)
            .limit(1)
        )
        return result.scalars().first() is not None

    async def contact_belongs_to_company(
        self,
        db: AsyncSession,
        contact_id: str,
        company_id: str,
        *,
        organization_id: str,
    ) -> bool:
        result = await db.execute(
            select(Contact.id)
            .where(
                Contact.id == contact_id,
                Contact.company_id == company_id,
                Contact.organization_id == organization_id,
            )
            .limit(1)
        )
        return result.scalars().first() is not None

    async def list_stages(
        self, db: AsyncSession, *, organization_id: str
    ) -> builtins.list[DealStage]:
        result = await db.execute(
            select(DealStage)
            .where(DealStage.organization_id == organization_id)
            .order_by(DealStage.order_index)
        )
        return list(result.scalars().all())

    async def create_stage(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        name: str,
        probability: float,
        order_index: int,
    ) -> DealStage:
        stage = DealStage(
            organization_id=organization_id,
            name=name,
            default_probability=probability,
            order_index=order_index,
        )
        db.add(stage)
        return stage

    async def get_deal_product(
        self,
        db: AsyncSession,
        *,
        deal_id: str,
        product_id: str,
        organization_id: str,
    ) -> DealProduct | None:
        result = await db.execute(
            select(DealProduct)
            .join(Deal, Deal.id == DealProduct.deal_id)
            .where(
                DealProduct.deal_id == deal_id,
                DealProduct.product_id == product_id,
                Deal.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_deal_products(
        self,
        db: AsyncSession,
        deal_id: str,
        *,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
    ) -> builtins.list[DealProduct]:
        stmt = (
            select(DealProduct)
            .join(Deal, Deal.id == DealProduct.deal_id)
            .where(
                DealProduct.deal_id == deal_id,
                Deal.organization_id == organization_id,
            )
            .order_by(DealProduct.id.asc())
        )
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_deal_products(
        self, db: AsyncSession, deal_id: str, *, organization_id: str
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(DealProduct)
            .join(Deal, Deal.id == DealProduct.deal_id)
            .where(DealProduct.deal_id == deal_id, Deal.organization_id == organization_id)
        )
        return int(result.scalar_one())

    async def create_deal_product(
        self, db: AsyncSession, *, deal_id: str, product_id: str, quantity: int, unit_price: float
    ) -> DealProduct:
        dp = DealProduct(
            deal_id=deal_id, product_id=product_id, quantity=quantity, unit_price=unit_price
        )
        db.add(dp)
        return dp

    async def delete_deal_product(self, db: AsyncSession, dp: DealProduct) -> None:
        await db.delete(dp)

    async def get_product(self, db: AsyncSession, product_id: str) -> Product | None:
        result = await db.execute(select(Product).where(Product.id == product_id))
        return result.scalars().first()

    async def get_product_by_name(self, db: AsyncSession, name: str) -> Product | None:
        result = await db.execute(select(Product).where(Product.name.ilike(name)).limit(1))
        return result.scalars().first()

    async def get_product_scoped(
        self, db: AsyncSession, *, product_id: str, organization_id: str
    ) -> Product | None:
        result = await db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_product_by_sku(
        self, db: AsyncSession, *, organization_id: str, sku: str
    ) -> Product | None:
        result = await db.execute(
            select(Product).where(
                Product.sku == sku,
                Product.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def save_product_snapshot(
        self,
        db: AsyncSession,
        line: DealProduct,
        *,
        product_name: str,
        quantity: int,
        unit_price: Decimal,
        discount_percent: Decimal,
        tax_percent: Decimal,
    ) -> None:
        line.product_name = product_name
        line.quantity = quantity
        line.unit_price = unit_price
        line.discount_percent = discount_percent
        line.tax_percent = tax_percent

    async def set_amount(self, db: AsyncSession, deal: Deal, amount: float) -> None:
        deal.amount = amount

    async def create_product(
        self, db: AsyncSession, *, organization_id: str, name: str, sku: str, price: float
    ) -> Product:
        product = Product(organization_id=organization_id, name=name, sku=sku, price=price)
        db.add(product)
        return product
