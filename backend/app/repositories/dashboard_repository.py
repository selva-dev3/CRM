from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallLog, Deal, Email, Lead, Meeting, Task


class DashboardRepository:
    """DB query layer for dashboard aggregate queries. No business logic here."""

    async def count_leads(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Lead.id)))
        return result.scalar() or 0

    async def sum_won_deals(self, db: AsyncSession) -> float:
        result = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(Deal.stage == "Closed Won")
        )
        return float(result.scalar() or 0.0)

    async def count_deals(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Deal.id)))
        return result.scalar() or 0

    async def count_won_deals(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Deal.id)).where(Deal.stage == "Closed Won"))
        return result.scalar() or 0

    async def avg_lead_score(self, db: AsyncSession) -> float:
        if not hasattr(Lead, "ai_score"):
            return 0.0
        result = await db.execute(select(func.coalesce(func.avg(Lead.ai_score), 0.0)))
        return round(float(result.scalar() or 0.0), 1)

    async def recent_leads(self, db: AsyncSession, limit: int = 3) -> list[Lead]:
        result = await db.execute(select(Lead).order_by(Lead.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def deal_stage_totals(self, db: AsyncSession) -> list[tuple]:
        result = await db.execute(
            select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)).group_by(
                Deal.stage
            )
        )
        return list(result.all())

    async def top_performers(self, db: AsyncSession, limit: int = 5) -> list[tuple]:
        result = await db.execute(
            select(Deal.assigned_to, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
            .where(Deal.assigned_to.isnot(None))
            .group_by(Deal.assigned_to)
            .order_by(func.sum(Deal.amount).desc())
            .limit(limit)
        )
        return list(result.all())

    async def lead_source_counts(self, db: AsyncSession) -> list[tuple]:
        result = await db.execute(select(Lead.source, func.count(Lead.id)).group_by(Lead.source))
        return list(result.all())

    async def count_converted_leads_by_source(self, db: AsyncSession, source: Optional[str]) -> int:
        result = await db.execute(
            select(func.count(Lead.id)).where(
                (Lead.source == source)
                & (Lead.status.ilike("%convert%") | Lead.status.ilike("%won%"))
            )
        )
        return result.scalar() or 0

    async def count_calls(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(CallLog.id)))
        return result.scalar() or 0

    async def count_emails(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Email.id)))
        return result.scalar() or 0

    async def count_meetings(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Meeting.id)))
        return result.scalar() or 0

    async def count_completed_tasks(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Task.id)).where(Task.status == "Completed"))
        return result.scalar() or 0

    async def recent_deals(self, db: AsyncSession, limit: int = 5) -> list[Deal]:
        result = await db.execute(select(Deal).order_by(Deal.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def count_deals_and_sum(self, db: AsyncSession) -> tuple[int, float]:
        result = await db.execute(select(func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)))
        row = result.first()
        return (row[0] if row else 0, float(row[1]) if row else 0.0)

    async def top_deal(self, db: AsyncSession) -> Optional[Deal]:
        result = await db.execute(select(Deal).order_by(Deal.amount.desc()).limit(1))
        return result.scalars().first()