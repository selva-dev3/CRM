from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, PriceBook, PriceBookEntry, Product


class PriceBookRepository:
    async def get_organization_currency(
        self, db: AsyncSession, *, organization_id: str
    ) -> str | None:
        return await db.scalar(
            select(Organization.currency).where(Organization.id == organization_id)
        )

    async def list(self, db: AsyncSession, *, organization_id: str) -> list[tuple[PriceBook, int]]:
        result = await db.execute(
            select(PriceBook, func.count(PriceBookEntry.id))
            .outerjoin(PriceBookEntry, PriceBookEntry.price_book_id == PriceBook.id)
            .where(PriceBook.organization_id == organization_id)
            .group_by(PriceBook.id)
            .order_by(PriceBook.is_default.desc(), PriceBook.name.asc())
        )
        return list(result.all())

    async def get(
        self, db: AsyncSession, *, price_book_id: str, organization_id: str
    ) -> PriceBook | None:
        return await db.scalar(
            select(PriceBook).where(
                PriceBook.id == price_book_id,
                PriceBook.organization_id == organization_id,
            )
        )

    async def unset_default(self, db: AsyncSession, organization_id: str) -> None:
        await db.execute(
            update(PriceBook)
            .where(PriceBook.organization_id == organization_id)
            .values(is_default=False)
        )

    async def list_entries(
        self, db: AsyncSession, *, price_book_id: str, organization_id: str
    ) -> list[tuple[PriceBookEntry, Product]]:
        result = await db.execute(
            select(PriceBookEntry, Product)
            .join(Product, Product.id == PriceBookEntry.product_id)
            .join(PriceBook, PriceBook.id == PriceBookEntry.price_book_id)
            .where(
                PriceBookEntry.price_book_id == price_book_id,
                PriceBook.organization_id == organization_id,
                Product.organization_id == organization_id,
            )
            .order_by(Product.name.asc())
        )
        return list(result.all())

    async def get_product(
        self, db: AsyncSession, *, product_id: str, organization_id: str
    ) -> Product | None:
        return await db.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.organization_id == organization_id,
            )
        )

    async def get_entry(
        self, db: AsyncSession, *, price_book_id: str, product_id: str
    ) -> PriceBookEntry | None:
        return await db.scalar(
            select(PriceBookEntry).where(
                PriceBookEntry.price_book_id == price_book_id,
                PriceBookEntry.product_id == product_id,
            )
        )


price_book_repository = PriceBookRepository()
