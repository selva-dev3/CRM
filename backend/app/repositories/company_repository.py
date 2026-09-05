from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company


class CompanyRepository:
    """DB query layer for the Company entity. No business logic here."""

    async def list_by_org(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> builtins.list[Company]:
        stmt = select(Company).where(Company.organization_id == organization_id)
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_org(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Company)
            .where(Company.organization_id == organization_id)
        )
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, db: AsyncSession, company_id: str) -> Company | None:
        result = await db.execute(select(Company).where(Company.id == company_id))
        return result.scalars().first()

    async def get_by_id_scoped(
        self, db: AsyncSession, *, company_id: str, organization_id: str
    ) -> Company | None:
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self,
        db: AsyncSession,
        ids: builtins.list[str],
        *,
        organization_id: str,
    ) -> builtins.list[Company]:
        result = await db.execute(
            select(Company).where(Company.id.in_(ids), Company.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Company:
        company = Company(**data)
        db.add(company)
        return company

    async def delete(self, db: AsyncSession, company: Company) -> None:
        await db.delete(company)
