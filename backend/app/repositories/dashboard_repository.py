from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallLog, Deal, Email, Lead, Meeting, Organization, Task


class DashboardRepository:
    """DB query layer for dashboard aggregate queries. No business logic here."""

    async def count_leads(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
            )
        )
        return result.scalar() or 0

    async def sum_pipeline_deals(self, db: AsyncSession, organization_id: str) -> float:
        result = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(("Closed Won", "Closed Lost")),
            )
        )
        return float(result.scalar() or 0.0)

    async def sum_won_deals(self, db: AsyncSession, organization_id: str) -> float:
        result = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage == "Closed Won",
            )
        )
        return float(result.scalar() or 0.0)

    async def count_closed_deals(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Deal.id)).where(
                Deal.organization_id == organization_id,
                Deal.stage.in_(("Closed Won", "Closed Lost")),
            )
        )
        return result.scalar() or 0

    async def count_won_deals(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Deal.id)).where(
                Deal.organization_id == organization_id,
                Deal.stage == "Closed Won",
            )
        )
        return result.scalar() or 0

    async def avg_lead_score(self, db: AsyncSession, organization_id: str) -> float:
        result = await db.execute(
            select(func.coalesce(func.avg(Lead.score), 0.0)).where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
            )
        )
        return round(float(result.scalar() or 0.0), 1)

    async def count_scored_leads(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
                Lead.score.isnot(None),
            )
        )
        return result.scalar() or 0

    async def recent_leads(
        self, db: AsyncSession, organization_id: str, limit: int = 3
    ) -> list[Lead]:
        result = await db.execute(
            select(Lead)
            .where(Lead.organization_id == organization_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def deal_stage_totals(self, db: AsyncSession, organization_id: str) -> list[tuple]:
        result = await db.execute(
            select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
            .where(Deal.organization_id == organization_id)
            .group_by(Deal.stage)
        )
        return list(result.all())

    async def top_performers(
        self, db: AsyncSession, organization_id: str, limit: int = 5
    ) -> list[tuple]:
        result = await db.execute(
            select(Deal.assigned_to, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
            .where(
                Deal.organization_id == organization_id,
                Deal.assigned_to.isnot(None),
                Deal.stage == "Closed Won",
            )
            .group_by(Deal.assigned_to)
            .order_by(func.sum(Deal.amount).desc())
            .limit(limit)
        )
        return list(result.all())

    async def lead_source_counts(self, db: AsyncSession, organization_id: str) -> list[tuple]:
        result = await db.execute(
            select(Lead.source, func.count(Lead.id))
            .where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
            )
            .group_by(Lead.source)
        )
        return list(result.all())

    async def count_converted_leads_by_source(
        self, db: AsyncSession, organization_id: str, source: str | None
    ) -> int:
        result = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
                Lead.source == source,
                Lead.status.ilike("%convert%") | Lead.status.ilike("%won%"),
            )
        )
        return result.scalar() or 0

    async def count_calls(
        self, db: AsyncSession, organization_id: str, start: datetime, end: datetime
    ) -> int:
        result = await db.execute(
            select(func.count(CallLog.id)).where(
                CallLog.organization_id == organization_id,
                CallLog.timestamp >= start,
                CallLog.timestamp < end,
            )
        )
        return result.scalar() or 0

    async def count_emails(
        self, db: AsyncSession, organization_id: str, start: datetime, end: datetime
    ) -> int:
        result = await db.execute(
            select(func.count(Email.id)).where(
                Email.organization_id == organization_id,
                Email.sent_at >= start,
                Email.sent_at < end,
                Email.status.ilike("sent"),
            )
        )
        return result.scalar() or 0

    async def count_meetings(
        self, db: AsyncSession, organization_id: str, start: datetime, end: datetime
    ) -> int:
        result = await db.execute(
            select(func.count(Meeting.id)).where(
                Meeting.organization_id == organization_id,
                Meeting.start_time >= start,
                Meeting.start_time < end,
            )
        )
        return result.scalar() or 0

    async def count_completed_tasks(
        self, db: AsyncSession, organization_id: str, start: datetime, end: datetime
    ) -> int:
        result = await db.execute(
            select(func.count(Task.id)).where(
                Task.organization_id == organization_id,
                Task.status == "Completed",
                Task.updated_at >= start,
                Task.updated_at < end,
            )
        )
        return result.scalar() or 0

    async def recent_deals(
        self, db: AsyncSession, organization_id: str, limit: int = 5
    ) -> list[Deal]:
        result = await db.execute(
            select(Deal)
            .where(Deal.organization_id == organization_id)
            .order_by(Deal.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_deals_and_sum(
        self, db: AsyncSession, organization_id: str
    ) -> tuple[int, float]:
        result = await db.execute(
            select(func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(("Closed Won", "Closed Lost")),
            )
        )
        row = result.first()
        return (row[0] if row else 0, float(row[1]) if row else 0.0)

    async def top_deal(self, db: AsyncSession, organization_id: str) -> Deal | None:
        result = await db.execute(
            select(Deal)
            .where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(("Closed Won", "Closed Lost")),
            )
            .order_by(Deal.amount.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_organization_timezone(self, db: AsyncSession, organization_id: str) -> str:
        result = await db.execute(
            select(Organization.timezone).where(Organization.id == organization_id)
        )
        return result.scalar() or "UTC"
