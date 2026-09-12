from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, Organization, Quote, SalesOrder, SalesOrderItem


class OrderRepository:
    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[SalesOrder]:
        conditions = [SalesOrder.organization_id == organization_id]
        if status:
            conditions.append(SalesOrder.status == status)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(SalesOrder.order_number.ilike(pattern))
        result = await db.execute(
            select(SalesOrder)
            .where(*conditions)
            .order_by(SalesOrder.created_at.desc(), SalesOrder.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(
        self, db: AsyncSession, *, organization_id: str, status=None, search=None
    ) -> int:
        conditions = [SalesOrder.organization_id == organization_id]
        if status:
            conditions.append(SalesOrder.status == status)
        if search and search.strip():
            conditions.append(SalesOrder.order_number.ilike(f"%{search.strip()}%"))
        return int(
            (
                await db.execute(select(func.count()).select_from(SalesOrder).where(*conditions))
            ).scalar_one()
        )

    async def get(
        self, db: AsyncSession, *, order_id: str, organization_id: str, lock: bool = False
    ) -> SalesOrder | None:
        query = select(SalesOrder).where(
            SalesOrder.id == order_id,
            SalesOrder.organization_id == organization_id,
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await db.scalar(query)

    async def get_by_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> SalesOrder | None:
        return await db.scalar(
            select(SalesOrder).where(
                SalesOrder.quote_id == quote_id,
                SalesOrder.organization_id == organization_id,
            )
        )

    async def get_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str, lock: bool = False
    ) -> Quote | None:
        query = select(Quote).where(
            Quote.id == quote_id,
            Quote.organization_id == organization_id,
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await db.scalar(query)

    async def get_invoice_for_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Invoice | None:
        return await db.scalar(
            select(Invoice).where(
                Invoice.quote_id == quote_id,
                Invoice.organization_id == organization_id,
            )
        )

    async def list_items(
        self, db: AsyncSession, *, order_id: str, organization_id: str
    ) -> list[SalesOrderItem]:
        result = await db.execute(
            select(SalesOrderItem)
            .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
            .where(
                SalesOrderItem.order_id == order_id,
                SalesOrder.organization_id == organization_id,
            )
            .order_by(SalesOrderItem.id)
        )
        return list(result.scalars().all())

    async def lock_numbering(self, db: AsyncSession, organization_id: str) -> Organization | None:
        return await db.scalar(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )


order_repository = OrderRepository()
