from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, InvoiceItem
from app.models.deal import Deal, DealProduct
from app.models.product import Product


class InvoiceRepository:
    """DB query layer for the Invoice domain. All queries are organization-scoped."""

    async def get_scoped(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.organization_id == organization_id
            )
        )
        return result.scalars().first()

    async def list_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Invoice]:
        stmt = select(Invoice).where(Invoice.organization_id == organization_id)
        if status and status.strip():
            stmt = stmt.where(Invoice.status == status.strip())
        if search and search.strip():
            stmt = stmt.where(Invoice.invoice_number.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Invoice.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_deal(self, db: AsyncSession, deal_id: str) -> Invoice | None:
        result = await db.execute(select(Invoice).where(Invoice.deal_id == deal_id))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> Invoice:
        invoice = Invoice(**data)
        db.add(invoice)
        return invoice

    async def add_items(self, db: AsyncSession, *, items: list[dict]) -> list[InvoiceItem]:
        rows = [InvoiceItem(**item) for item in items]
        db.add_all(rows)
        return rows

    async def list_items(self, db: AsyncSession, invoice_id: str) -> list[InvoiceItem]:
        result = await db.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))
        return list(result.scalars().all())

    async def delete(self, db: AsyncSession, invoice: Invoice) -> None:
        await db.delete(invoice)

    # --- deal / product lookups used by the conversion flow ---

    async def get_deal_scoped(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> Deal | None:
        result = await db.execute(
            select(Deal).where(Deal.id == deal_id, Deal.organization_id == organization_id)
        )
        return result.scalars().first()

    async def list_deal_products(self, db: AsyncSession, deal_id: str) -> list[DealProduct]:
        result = await db.execute(select(DealProduct).where(DealProduct.deal_id == deal_id))
        return list(result.scalars().all())

    async def get_product_scoped(
        self, db: AsyncSession, *, product_id: str, organization_id: str
    ) -> Product | None:
        result = await db.execute(
            select(Product).where(
                Product.id == product_id, Product.organization_id == organization_id
            )
        )
        return result.scalars().first()


invoice_repository = InvoiceRepository()
