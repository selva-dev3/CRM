from __future__ import annotations

import builtins

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company


class CompanyRepository:
    """DB query layer for the Company entity. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> builtins.list[Company]:
        stmt = select(Company).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, company_id: str) -> Company | None:
        result = await db.execute(select(Company).where(Company.id == company_id))
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str]
    ) -> builtins.list[Company]:
        result = await db.execute(select(Company).where(Company.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Company:
        company = Company(**data)
        db.add(company)
        return company

    async def delete(self, db: AsyncSession, company: Company) -> None:
        await db.delete(company)
