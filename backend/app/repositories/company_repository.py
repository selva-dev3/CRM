from __future__ import annotations

from typing import Optional

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
        search: Optional[str] = None,
    ) -> list[Company]:
        stmt = select(Company).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, company_id: str) -> Optional[Company]:
        result = await db.execute(select(Company).where(Company.id == company_id))
        return result.scalars().first()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[Company]:
        result = await db.execute(select(Company).where(Company.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Company:
        company = Company(**data)
        db.add(company)
        return company

    async def delete(self, db: AsyncSession, company: Company) -> None:
        await db.delete(company)