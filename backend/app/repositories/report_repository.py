from typing import Any, Optional, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CallLog,
    Company,
    CustomReport,
    Deal,
    Email,
    Lead,
    Meeting,
    ReportExport,
    ScheduledReport,
    User,
)


class ReportRepository:
    """Query layer for report aggregation and report entity persistence."""

    async def get_org_id(self, db: AsyncSession, current_user: Optional[Any] = None) -> str:
        from app.api.v1.deps import get_valid_org_id

        return await get_valid_org_id(db, current_user)

    # --- Sales Performance ---
    async def total_won_revenue(self, db: AsyncSession, org_id: str) -> float:
        res = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == org_id, Deal.stage == "Closed Won"
            )
        )
        return float(res.scalar() or 0.0)

    async def rep_performance(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                User.name,
                User.role,
                func.count(Deal.id).label("deals_assigned"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", 1), else_=0)), 0).label("deals_closed"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)), 0.0).label("revenue"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.role)
            .order_by(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)).desc())
        )
        res = await db.execute(query)
        return res.all()

    # --- Pipeline Velocity ---
    async def deals_by_stage(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                Deal.stage,
                func.count(Deal.id).label("deal_count"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("total_value"),
            )
            .where(Deal.organization_id == org_id)
            .group_by(Deal.stage)
        )
        res = await db.execute(query)
        return res.all()

    # --- Win / Loss ---
    async def count_deals_in_stage(self, db: AsyncSession, org_id: str, stage: str) -> int:
        res = await db.execute(
            select(func.count(Deal.id)).where(Deal.organization_id == org_id, Deal.stage == stage)
        )
        return res.scalar() or 0

    async def win_loss_by_industry(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                Company.industry,
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", 1), else_=0)), 0).label("won"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Lost", 1), else_=0)), 0).label("lost"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)), 0.0).label("won_val"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Lost", Deal.amount), else_=0.0)), 0.0).label("lost_val"),
            )
            .join(Company, Deal.company_id == Company.id)
            .where(Deal.organization_id == org_id)
            .group_by(Company.industry)
        )
        res = await db.execute(query)
        return res.all()

    # --- Lead Attribution ---
    async def leads_by_source(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                Lead.source,
                func.count(Lead.id).label("total_leads"),
                func.coalesce(func.sum(case((Lead.status == "Converted", 1), else_=0)), 0).label("converted_leads"),
                func.coalesce(func.avg(Lead.score), 0.0).label("avg_score"),
            )
            .where(Lead.organization_id == org_id)
            .group_by(Lead.source)
        )
        res = await db.execute(query)
        return res.all()

    # --- Rep Leaderboard ---
    async def rep_leaderboard(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                User.name,
                User.email,
                User.role,
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", 1), else_=0)), 0).label("deals"),
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)), 0.0).label("revenue"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.email, User.role)
            .order_by(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)).desc())
        )
        res = await db.execute(query)
        return res.all()

    # --- Revenue Forecasting ---
    async def revenue_forecast(self, db: AsyncSession, org_id: str) -> Optional[Any]:
        query = (
            select(
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)), 0.0).label("committed"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("total_pipeline"),
                func.coalesce(func.sum(Deal.amount * (Deal.probability / 100.0)), 0.0).label("weighted"),
            ).where(Deal.organization_id == org_id)
        )
        res = await db.execute(query)
        return res.one_or_none()

    # --- Activity Metrics ---
    async def count_calls(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(CallLog.id)).where(CallLog.organization_id == org_id))
        return res.scalar() or 0

    async def count_emails(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(Email.id)).where(Email.organization_id == org_id))
        return res.scalar() or 0

    async def count_meetings(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(Meeting.id)).where(Meeting.organization_id == org_id))
        return res.scalar() or 0

    async def org_users(self, db: AsyncSession, org_id: str) -> list[Any]:
        res = await db.execute(select(User.name, User.role).where(User.organization_id == org_id))
        return res.all()

    # --- Deal Duration / CAC / LTV / Churn ---
    async def count_deals(self, db: AsyncSession, org_id: str) -> int:
        res = await db.execute(select(func.count(Deal.id)).where(Deal.organization_id == org_id))
        return res.scalar() or 0

    async def won_aggregate(self, db: AsyncSession, org_id: str) -> Optional[Any]:
        query = (
            select(
                func.count(Deal.id).label("won_cnt"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("tot_rev"),
            ).where(Deal.organization_id == org_id, Deal.stage == "Closed Won")
        )
        res = await db.execute(query)
        return res.one_or_none()

    async def lost_aggregate(self, db: AsyncSession, org_id: str) -> Optional[Any]:
        query = (
            select(
                func.count(Deal.id).label("lost_cnt"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("lost_arr"),
            ).where(Deal.organization_id == org_id, Deal.stage == "Closed Lost")
        )
        res = await db.execute(query)
        return res.one_or_none()

    # --- Quota Attainment ---
    async def rep_quota(self, db: AsyncSession, org_id: str) -> list[Any]:
        query = (
            select(
                User.name,
                User.role,
                func.coalesce(func.sum(case((Deal.stage == "Closed Won", Deal.amount), else_=0.0)), 0.0).label("revenue"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("pipeline"),
            )
            .join(Deal, Deal.assigned_to == User.id)
            .where(Deal.organization_id == org_id)
            .group_by(User.id, User.name, User.role)
        )
        res = await db.execute(query)
        return res.all()

    # --- Custom Reports ---
    async def list_custom_reports(self, db: AsyncSession, org_id: str) -> Sequence[CustomReport]:
        stmt = select(CustomReport).where(CustomReport.organization_id == org_id).order_by(CustomReport.created_at.desc())
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_custom_report(self, db: AsyncSession, report_id: str, org_id: str) -> Optional[CustomReport]:
        stmt = select(CustomReport).where(CustomReport.id == report_id, CustomReport.organization_id == org_id)
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

    async def deals_for_csv(self, db: AsyncSession, org_id: str) -> list[Any]:
        res = await db.execute(
            select(Deal.title, Deal.amount, Deal.stage).where(Deal.organization_id == org_id).limit(50)
        )
        return res.all()

    # --- Scheduled Reports ---
    async def create_scheduled_report(self, db: AsyncSession, *, data: dict) -> ScheduledReport:
        report = ScheduledReport(**data)
        db.add(report)
        return report

    async def list_scheduled_reports(self, db: AsyncSession, org_id: str) -> Sequence[ScheduledReport]:
        stmt = select(ScheduledReport).where(ScheduledReport.organization_id == org_id).order_by(ScheduledReport.created_at.desc())
        res = await db.execute(stmt)
        return res.scalars().all()