from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductCategory


class ProductRepository:
    """Persistence operations for the tenant product catalog."""

    @staticmethod
    def _filters(
        organization_id: str, *, search: str | None = None, category: str | None = None
    ) -> builtins.list:
        filters = [Product.organization_id == organization_id]
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(Product.name.ilike(term) | Product.sku.ilike(term))
        if category and category.strip():
            filters.append(func.lower(ProductCategory.name) == category.strip().lower())
        return filters

    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        category: str | None = None,
    ) -> builtins.list[tuple[Product, str | None]]:
        result = await db.execute(
            select(Product, ProductCategory.name)
            .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
            .where(*self._filters(organization_id, search=search, category=category))
            .order_by(Product.name, Product.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [(product, category_name) for product, category_name in result.tuples()]

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        category: str | None = None,
    ) -> int:
        return int(
            await db.scalar(
                select(func.count())
                .select_from(Product)
                .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
                .where(*self._filters(organization_id, search=search, category=category))
            )
            or 0
        )

    async def category_id(self, db: AsyncSession, *, organization_id: str, name: str) -> str | None:
        return await db.scalar(
            select(ProductCategory.id).where(
                ProductCategory.organization_id == organization_id,
                func.lower(func.btrim(ProductCategory.name)) == name.strip().lower(),
            )
        )

    async def list_categories(
        self, db: AsyncSession, *, organization_id: str
    ) -> builtins.list[ProductCategory]:
        result = await db.execute(
            select(ProductCategory)
            .where(ProductCategory.organization_id == organization_id)
            .order_by(ProductCategory.name, ProductCategory.id)
        )
        return builtins.list(result.scalars().all())

    async def get(
        self,
        db: AsyncSession,
        *,
        product_id: str,
        organization_id: str,
        lock: bool = False,
    ) -> Product | None:
        stmt = select(Product).where(
            Product.id == product_id, Product.organization_id == organization_id
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_with_category(
        self, db: AsyncSession, *, product_id: str, organization_id: str
    ) -> tuple[Product, str | None] | None:
        row = (
            (
                await db.execute(
                    select(Product, ProductCategory.name)
                    .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
                    .where(Product.id == product_id, Product.organization_id == organization_id)
                )
            )
            .tuples()
            .first()
        )
        return (row[0], row[1]) if row else None

    async def list_by_ids(
        self, db: AsyncSession, *, ids: builtins.list[str], organization_id: str
    ) -> builtins.list[Product]:
        result = await db.execute(
            select(Product).where(Product.id.in_(ids), Product.organization_id == organization_id)
        )
        return builtins.list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Product:
        product = Product(**data)
        db.add(product)
        return product

    async def create_category(
        self, db: AsyncSession, *, organization_id: str, name: str
    ) -> ProductCategory:
        category = ProductCategory(organization_id=organization_id, name=name)
        db.add(category)
        return category

    async def delete(self, db: AsyncSession, product: Product) -> None:
        await db.delete(product)


product_repository = ProductRepository()
