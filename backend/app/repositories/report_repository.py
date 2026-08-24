from collections.abc import Sequence
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CallLog,
    Company,
    CustomReport,
    Deal,
    Email,
    EmailLog,
    Lead,
    Meeting,
    ReportExport,
    ScheduledReport,
    User,
    UserQuota,
)

CLOSED_WON_STAGE = "Closed Won"
CLOSED_LOST_STAGE = "Closed Lost"
OPEN_STAGES_EXCLUSION = (CLOSED_WON_STAGE, CLOSED_LOST_STAGE)

# Seconds-per-day helper applied in Python to keep SQL portable.
_SECONDS_PER_DAY = 86400.0


def _epoch_diff(col_end: Any, col_start: Any) -> Any:
    """Seconds elapsed between two timestamp columns (portable across PG drivers)."""
    return func.extract("epoch", col_end - col_start)


class ReportRepository:
    """Query layer for report aggregation and report entity persistence."""

    # --- Sales Performance ---
    async def total_won_revenue(self, db: AsyncSession, org_id: str) -> float:
        res = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == org_id, Deal.stage == CLOSED_WON_STAGE
            )
        )
        return float(res.scalar() or 0.0)

    async def quotas_by_user(self, db: AsyncSession, org_id: str) -> dict[str, float]:
        res = await db.execute(
            select(UserQuota.user_id, UserQuota.target_amount).where(
                UserQuota.organization_id == org_id
            )
        )
        return {user_id: float(amount) for user_id, amount in res.all()}

    async def rep_performance(self, db: AsyncSession, org_id: str, limit: int = 100) -> list[Any]:
        query = (
            select(
                User.id,
                User.name,
                User.role,
                func.count(Deal.id).label("deals_assigned"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, 1), else_=0)), 0
                ).label("deals_closed"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)), 0.0
                ).label("revenue"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.role)
            .order_by(
                func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)).desc()
            )
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Pipeline Velocity ---
    async def stage_age_breakdown(self, db: AsyncSession, org_id: str) -> list[Any]:
        """Per open stage: deal count, value, and average age (seconds) of the
        deals currently sitting in that stage."""
        query = (
            select(
                Deal.stage,
                func.count(Deal.id).label("deal_count"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("total_value"),
                func.coalesce(func.avg(_epoch_diff(func.now(), Deal.created_at)), 0.0).label(
                    "avg_age_seconds"
                ),
            )
            .where(Deal.organization_id == org_id, Deal.stage.not_in(OPEN_STAGES_EXCLUSION))
            .group_by(Deal.stage)
        )
        res = await db.execute(query)
        return list(res.all())

    async def closed_cycle_stats(self, db: AsyncSession, org_id: str) -> Any | None:
        """Creation-to-last-update cycle length (seconds) of Closed Won deals.

        ``updated_at`` is the closest persisted proxy for the close event;
        the schema has no dedicated ``closed_at`` column or stage history.
        """
        cycle_expr = _epoch_diff(Deal.updated_at, Deal.created_at)
        query = select(
            func.count(Deal.id).label("closed_cnt"),
            func.coalesce(func.min(cycle_expr), 0.0).label("fastest_sec"),
            func.coalesce(func.max(cycle_expr), 0.0).label("longest_sec"),
            func.coalesce(func.avg(cycle_expr), 0.0).label("avg_sec"),
        ).where(Deal.organization_id == org_id, Deal.stage == CLOSED_WON_STAGE)
        res = await db.execute(query)
        return res.one_or_none()

    # --- Win / Loss ---
    async def count_deals_in_stage(self, db: AsyncSession, org_id: str, stage: str) -> int:
        res = await db.execute(
            select(func.count(Deal.id)).where(Deal.organization_id == org_id, Deal.stage == stage)
        )
        return res.scalar() or 0

    async def win_loss_by_industry(
        self, db: AsyncSession, org_id: str, limit: int = 50
    ) -> list[Any]:
        query = (
            select(
                Company.industry,
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, 1), else_=0)), 0
                ).label("won"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_LOST_STAGE, 1), else_=0)), 0
                ).label("lost"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)), 0.0
                ).label("won_val"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_LOST_STAGE, Deal.amount), else_=0.0)), 0.0
                ).label("lost_val"),
            )
            .join(Company, Deal.company_id == Company.id)
            .where(Deal.organization_id == org_id)
            .group_by(Company.industry)
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    async def top_loss_reason(self, db: AsyncSession, org_id: str) -> str | None:
        """Most frequent persisted loss reason among Closed Lost deals."""
        res = await db.execute(
            select(Deal.loss_reason, func.count(Deal.id).label("cnt"))
            .where(
                Deal.organization_id == org_id,
                Deal.stage == CLOSED_LOST_STAGE,
                Deal.loss_reason.is_not(None),
                func.length(Deal.loss_reason) > 0,
            )
            .group_by(Deal.loss_reason)
            .order_by(func.count(Deal.id).desc())
            .limit(1)
        )
        row = res.first()
        return row[0] if row else None

    # --- Lead Attribution ---
    async def leads_by_source(self, db: AsyncSession, org_id: str, limit: int = 50) -> list[Any]:
        query = (
            select(
                Lead.source,
                func.count(Lead.id).label("total_leads"),
                func.coalesce(func.sum(case((Lead.status == "Converted", 1), else_=0)), 0).label(
                    "converted_leads"
                ),
                func.coalesce(func.avg(Lead.score), 0.0).label("avg_score"),
            )
            .where(Lead.organization_id == org_id)
            .group_by(Lead.source)
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Rep Leaderboard ---
    async def rep_leaderboard(self, db: AsyncSession, org_id: str, limit: int = 100) -> list[Any]:
        query = (
            select(
                User.id,
                User.name,
                User.email,
                User.role,
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, 1), else_=0)), 0
                ).label("deals"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)), 0.0
                ).label("revenue"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.email, User.role)
            .order_by(
                func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)).desc()
            )
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Revenue Forecasting ---
    async def revenue_forecast(self, db: AsyncSession, org_id: str) -> Any | None:
        """Open-pipeline totals plus weighted pipeline; closed deals excluded."""
        query = select(
            func.coalesce(func.sum(Deal.amount), 0.0).label("total_pipeline"),
            func.coalesce(func.sum(Deal.amount * (Deal.probability / 100.0)), 0.0).label(
                "weighted"
            ),
        ).where(Deal.organization_id == org_id, Deal.stage.not_in(OPEN_STAGES_EXCLUSION))
        res = await db.execute(query)
        return res.one_or_none()

    async def forecast_by_period(self, db: AsyncSession, org_id: str) -> list[Any]:
        """Open pipeline grouped by quarter of each deal's expected close date."""
        quarter = func.date_trunc("quarter", Deal.expected_close_date)
        query = (
            select(
                func.to_char(quarter, 'YYYY-"Q"Q').label("period"),
                func.count(Deal.id).label("deal_count"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("pipeline_amount"),
                func.coalesce(func.sum(Deal.amount * (Deal.probability / 100.0)), 0.0).label(
                    "weighted_amount"
                ),
            )
            .where(
                Deal.organization_id == org_id,
                Deal.stage.not_in(OPEN_STAGES_EXCLUSION),
                Deal.expected_close_date.is_not(None),
            )
            .group_by(quarter)
            .order_by(quarter)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Activity Metrics ---
    async def count_calls(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(
            select(func.count(CallLog.id)).where(CallLog.organization_id == org_id)
        )
        return res.scalar() or 0

    async def total_call_duration_seconds(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(
            select(func.coalesce(func.sum(CallLog.duration_seconds), 0)).where(
                CallLog.organization_id == org_id
            )
        )
        return int(res.scalar() or 0)

    async def count_emails(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(Email.id)).where(Email.organization_id == org_id))
        return res.scalar() or 0

    async def count_opened_emails(self, db: AsyncSession, org_id: str) -> int:
        """Distinct logged emails that have at least one 'opened' tracking event."""
        res = await db.execute(
            select(func.count(func.distinct(EmailLog.email_id)))
            .join(Email, Email.id == EmailLog.email_id)
            .where(Email.organization_id == org_id, EmailLog.event_type == "opened")
        )
        return res.scalar() or 0

    async def count_meetings(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(
            select(func.count(Meeting.id)).where(Meeting.organization_id == org_id)
        )
        return res.scalar() or 0

    # --- Deal Duration / CAC / LTV / Churn ---
    async def count_deals(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(Deal.id)).where(Deal.organization_id == org_id))
        return res.scalar() or 0

    async def won_aggregate(self, db: AsyncSession, org_id: str) -> Any | None:
        query = select(
            func.count(Deal.id).label("won_cnt"),
            func.coalesce(func.sum(Deal.amount), 0.0).label("tot_rev"),
        ).where(Deal.organization_id == org_id, Deal.stage == CLOSED_WON_STAGE)
        res = await db.execute(query)
        return res.one_or_none()

    async def lost_aggregate(self, db: AsyncSession, org_id: str) -> Any | None:
        query = select(
            func.count(Deal.id).label("lost_cnt"),
            func.coalesce(func.sum(Deal.amount), 0.0).label("lost_arr"),
        ).where(Deal.organization_id == org_id, Deal.stage == CLOSED_LOST_STAGE)
        res = await db.execute(query)
        return res.one_or_none()

    # --- Quota Attainment ---
    async def rep_quota(self, db: AsyncSession, org_id: str, limit: int = 100) -> list[Any]:
        open_amount = case((Deal.stage.not_in(OPEN_STAGES_EXCLUSION), Deal.amount), else_=0.0)
        query = (
            select(
                User.id,
                User.name,
                User.role,
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)), 0.0
                ).label("revenue"),
                func.coalesce(func.sum(open_amount), 0.0).label("pipeline"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.role)
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Custom Reports ---
    async def list_custom_reports(
        self, db: AsyncSession, org_id: str, *, limit: int = 20, offset: int = 0
    ) -> Sequence[CustomReport]:
        stmt = (
            select(CustomReport)
            .where(CustomReport.organization_id == org_id)
            .order_by(CustomReport.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_custom_report(
        self, db: AsyncSession, report_id: str, org_id: str
    ) -> CustomReport | None:
        stmt = select(CustomReport).where(
            CustomReport.id == report_id, CustomReport.organization_id == org_id
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_custom_report(self, db: AsyncSession, *, data: dict) -> CustomReport:
        report = CustomReport(**data)
        db.add(report)
        return report

    async def delete_custom_report(self, db: AsyncSession, report: CustomReport) -> None:
        await db.delete(report)

    # --- Exports ---
    async def create_export(self, db: AsyncSession, *, data: dict) -> ReportExport:
        export = ReportExport(**data)
        db.add(export)
        return export

    async def get_export(
        self, db: AsyncSession, export_id: str, org_id: str
    ) -> ReportExport | None:
        stmt = select(ReportExport).where(
            ReportExport.id == export_id,
            ReportExport.organization_id == org_id,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    # --- Scheduled Reports ---
    async def create_scheduled_report(self, db: AsyncSession, *, data: dict) -> ScheduledReport:
        report = ScheduledReport(**data)
        db.add(report)
        return report

    async def list_scheduled_reports(
        self, db: AsyncSession, org_id: str, *, limit: int = 20, offset: int = 0
    ) -> Sequence[ScheduledReport]:
        stmt = (
            select(ScheduledReport)
            .where(ScheduledReport.organization_id == org_id)
            .order_by(ScheduledReport.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_scheduled_report(
        self, db: AsyncSession, schedule_id: str, org_id: str
    ) -> ScheduledReport | None:
        stmt = select(ScheduledReport).where(
            ScheduledReport.id == schedule_id, ScheduledReport.organization_id == org_id
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_scheduled_report(self, db: AsyncSession, report: ScheduledReport) -> None:
        await db.delete(report)
