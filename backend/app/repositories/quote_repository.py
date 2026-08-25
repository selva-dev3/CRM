from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Quote


class QuoteRepository:
    """Database access for quotes, with explicit organization scoping."""

    async def list_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Quote]:
        stmt = select(Quote).where(Quote.organization_id == organization_id)
        if status and status.strip():
            stmt = stmt.where(Quote.status == status.strip())
        if search and search.strip():
            stmt = stmt.where(Quote.quote_number.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Quote.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_scoped(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Quote | None:
        result = await db.execute(
            select(Quote).where(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[Quote]:
        result = await db.execute(
            select(Quote)
            .where(
                Quote.deal_id == deal_id,
                Quote.organization_id == organization_id,
            )
            .order_by(Quote.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Quote:
        quote = Quote(**data)
        db.add(quote)
        return quote

    async def delete_scoped(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> bool:
        result = await db.execute(
            delete(Quote).where(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
        )
        return bool(result.rowcount)

    async def bulk_delete_scoped(
        self, db: AsyncSession, *, quote_ids: list[str], organization_id: str
    ) -> int:
        if not quote_ids:
            return 0
        result = await db.execute(
            delete(Quote).where(
                Quote.id.in_(quote_ids),
                Quote.organization_id == organization_id,
            )
        )
        return int(result.rowcount or 0)


quote_repository = QuoteRepository()
