from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.organization import Organization


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

    async def list_subsidiaries(
        self, db: AsyncSession, *, parent_company_id: str, organization_id: str
    ) -> list[Company]:
        result = await db.execute(
            select(Company)
            .where(
                Company.parent_company_id == parent_company_id,
                Company.organization_id == organization_id,
            )
            .order_by(Company.name.asc())
        )
        return list(result.scalars().all())

    async def set_parent(self, company: Company, parent_company_id: str | None) -> None:
        company.parent_company_id = parent_company_id

    async def create(self, db: AsyncSession, *, data: dict) -> Company:
        company = Company(**data)
        db.add(company)
        return company

    async def delete(self, db: AsyncSession, company: Company) -> None:
        await db.delete(company)

    async def lock_organization(self, db: AsyncSession, organization_id: str) -> None:
        await db.scalar(
            select(Organization.id).where(Organization.id == organization_id).with_for_update()
        )

    async def find_duplicate(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        normalized_name: str,
        normalized_domain: str | None,
        exclude_id: str | None = None,
    ) -> Company | None:
        stmt = select(Company).where(
            Company.organization_id == organization_id,
            func.lower(func.trim(Company.name)) == normalized_name,
        )
        if normalized_domain:
            stmt = select(Company).where(
                Company.organization_id == organization_id,
                func.lower(Company.website).contains(normalized_domain),
            )
        if exclude_id:
            stmt = stmt.where(Company.id != exclude_id)
        return (await db.execute(stmt.limit(1))).scalars().first()
