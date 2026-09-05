from __future__ import annotations

import builtins
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Contact, User
from app.models.deal import Deal, DealActivity, DealProduct, DealStage
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
    ) -> builtins.list[Deal]:
        stmt = select(Deal).where(Deal.organization_id == organization_id)
        if search and search.strip():
            stmt = stmt.where(Deal.title.ilike(f"%{search.strip()}%"))
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        stmt = stmt.order_by(Deal.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, db: AsyncSession, *, organization_id: str) -> builtins.list[Deal]:
        result = await db.execute(
            select(Deal)
            .where(Deal.organization_id == organization_id)
            .order_by(Deal.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, deal_id: str) -> Deal | None:
        result = await db.execute(select(Deal).where(Deal.id == deal_id))
        return result.scalars().first()

    async def get_by_id_scoped(
        self, db: AsyncSession, *, deal_id: str, organization_id: str, lock: bool = False
    ) -> Deal | None:
        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.organization_id == organization_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def set_won(self, db: AsyncSession, deal: Deal, amount: float) -> None:
        deal.stage = "Closed Won"
        deal.probability = 100
        deal.amount = amount

    async def add_activity(
        self, db: AsyncSession, *, deal_id: str, action: str, actor_id: str | None
    ) -> DealActivity:
        activity = DealActivity(deal_id=deal_id, action=action, performed_by=actor_id)
        db.add(activity)
        return activity

    async def list_activities(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> builtins.list[DealActivity]:
        result = await db.execute(
            select(DealActivity)
            .join(Deal, Deal.id == DealActivity.deal_id)
            .where(
                DealActivity.deal_id == deal_id,
                Deal.organization_id == organization_id,
            )
            .order_by(DealActivity.timestamp.desc())
        )
        return list(result.scalars().all())

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
        self, db: AsyncSession, ids: builtins.list[str], *, organization_id: str
    ) -> builtins.list[Deal]:
        result = await db.execute(
            select(Deal).where(Deal.id.in_(ids), Deal.organization_id == organization_id)
        )
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
        self, db: AsyncSession, *, organization_id: str, name: str, probability: float
    ) -> DealStage:
        stage = DealStage(
            organization_id=organization_id, name=name, default_probability=probability
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
        self, db: AsyncSession, deal_id: str, *, organization_id: str
    ) -> builtins.list[DealProduct]:
        result = await db.execute(
            select(DealProduct)
            .join(Deal, Deal.id == DealProduct.deal_id)
            .where(
                DealProduct.deal_id == deal_id,
                Deal.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

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
