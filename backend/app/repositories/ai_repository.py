from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Deal, Lead


class AIRepository:
    """Query layer for entities used by AI features — no business logic."""

    async def get_lead(self, db: AsyncSession, lead_id: str) -> Optional[Lead]:
        res = await db.execute(select(Lead).where(Lead.id == lead_id))
        return res.scalars().first()

    async def list_all_leads(self, db: AsyncSession) -> Sequence[Lead]:
        res = await db.execute(select(Lead))
        return res.scalars().all()

    async def get_deal(self, db: AsyncSession, deal_id: str) -> Optional[Deal]:
        res = await db.execute(select(Deal).where(Deal.id == deal_id))
        return res.scalars().first()

    async def get_company(self, db: AsyncSession, company_id: str) -> Optional[Company]:
        res = await db.execute(select(Company).where(Company.id == company_id))
        return res.scalars().first()