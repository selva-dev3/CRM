from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import (
    CallLog,
    Company,
    CustomReport,
    Deal,
    DealStageHistory,
    Email,
    EmailLog,
    Invoice,
    Lead,
    Meeting,
    Organization,
    Payment,
    Quote,
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

    @staticmethod
    def _scoped(
        filters: list[Any],
        access: RecordAccessContext | None,
        *,
        assigned: Any,
        created: Any,
    ) -> list[Any]:
        access_filter = record_access_filter(
            access, assigned_column=assigned, created_column=created
        )
        return [*filters, access_filter] if access_filter is not None else filters

    async def organization_currency(self, db: AsyncSession, org_id: str) -> str:
        result = await db.execute(select(Organization.currency).where(Organization.id == org_id))
        return (result.scalar_one_or_none() or "USD").upper()

    # --- Sales Performance ---
    async def total_won_revenue(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> float:
        filters = self._scoped(
            [Deal.organization_id == org_id, Deal.stage == CLOSED_WON_STAGE],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        res = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(*filters)
        )
        return float(res.scalar() or 0.0)

    async def quotas_by_user(self, db: AsyncSession, org_id: str) -> dict[str, float]:
        res = await db.execute(
            select(UserQuota.user_id, UserQuota.target_amount).where(
                UserQuota.organization_id == org_id
            )
            # Stable insertion order -> deterministic float summation order.
            .order_by(UserQuota.user_id.asc())
        )
        return {user_id: float(amount) for user_id, amount in res.all()}

    async def rep_performance(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 100,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        filters = self._scoped(
            [Deal.organization_id == org_id, User.organization_id == org_id],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
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
            .where(*filters)
            .group_by(User.id, User.name, User.role)
            .order_by(
                func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)).desc(),
                User.name.asc(),
                User.id.asc(),
            )
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Pipeline Velocity ---
    async def stage_age_breakdown(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> list[Any]:
        """Per open stage: deal count, value, and average age (seconds) of the
        deals currently sitting in that stage."""
        filters = self._scoped(
            [
                Deal.organization_id == org_id,
                DealStageHistory.stage.not_in(OPEN_STAGES_EXCLUSION),
            ],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = (
            select(
                DealStageHistory.stage,
                func.count(Deal.id).label("deal_count"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("total_value"),
                func.coalesce(
                    func.avg(_epoch_diff(func.now(), DealStageHistory.entered_at)), 0.0
                ).label("avg_age_seconds"),
            )
            .join(
                DealStageHistory,
                (DealStageHistory.deal_id == Deal.id)
                & (DealStageHistory.organization_id == org_id)
                & DealStageHistory.exited_at.is_(None),
            )
            .where(*filters)
            .group_by(DealStageHistory.stage)
            # Deterministic output order for exports/reports (run-to-run stable).
            .order_by(DealStageHistory.stage.asc())
        )
        res = await db.execute(query)
        return list(res.all())

    async def closed_cycle_stats(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> Any | None:
        """Creation-to-close cycle length (seconds) of Closed Won deals."""
        cycle_expr = _epoch_diff(Deal.closed_at, Deal.created_at)
        filters = self._scoped(
            [
                Deal.organization_id == org_id,
                Deal.stage == CLOSED_WON_STAGE,
                Deal.closed_at.is_not(None),
            ],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = select(
            func.count(Deal.id).label("closed_cnt"),
            func.coalesce(func.min(cycle_expr), 0.0).label("fastest_sec"),
            func.coalesce(func.max(cycle_expr), 0.0).label("longest_sec"),
            func.coalesce(func.avg(cycle_expr), 0.0).label("avg_sec"),
        ).where(*filters)
        res = await db.execute(query)
        return res.one_or_none()

    # --- Win / Loss ---
    async def count_deals_in_stage(
        self,
        db: AsyncSession,
        org_id: str,
        stage: str,
        access: RecordAccessContext | None = None,
    ) -> int:
        filters = self._scoped(
            [Deal.organization_id == org_id, Deal.stage == stage],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        res = await db.execute(
            select(func.count(Deal.id)).where(*filters)
        )
        return res.scalar() or 0

    async def win_loss_by_industry(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 50,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        filters = self._scoped(
            [Deal.organization_id == org_id, Company.organization_id == org_id],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
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
            .where(*filters)
            .group_by(Company.industry)
            .order_by(Company.industry.asc())
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    async def top_loss_reason(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> str | None:
        """Most frequent persisted loss reason among Closed Lost deals."""
        filters = self._scoped(
            [
                Deal.organization_id == org_id,
                Deal.stage == CLOSED_LOST_STAGE,
                Deal.loss_reason.is_not(None),
                func.length(Deal.loss_reason) > 0,
            ],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        res = await db.execute(
            select(Deal.loss_reason, func.count(Deal.id).label("cnt"))
            .where(*filters)
            .group_by(Deal.loss_reason)
            .order_by(func.count(Deal.id).desc())
            .limit(1)
        )
        row = res.first()
        return row[0] if row else None

    async def loss_reason_by_industry(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 200,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        """Loss-reason counts per company industry among Closed Lost deals."""
        filters = self._scoped(
            [
                Deal.organization_id == org_id,
                Company.organization_id == org_id,
                Deal.stage == CLOSED_LOST_STAGE,
                Deal.loss_reason.is_not(None),
                func.length(Deal.loss_reason) > 0,
            ],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = (
            select(
                Company.industry,
                Deal.loss_reason,
                func.count(Deal.id).label("cnt"),
            )
            .join(Company, Deal.company_id == Company.id)
            .where(*filters)
            .group_by(Company.industry, Deal.loss_reason)
            .order_by(Company.industry.asc(), Deal.loss_reason.asc())
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Lead Attribution ---
    async def leads_by_source(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 50,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        filters = self._scoped(
            [Lead.organization_id == org_id, Lead.is_archived.is_(False)],
            access,
            assigned=Lead.assigned_to,
            created=Lead.created_by,
        )
        query = (
            select(
                Lead.source,
                func.count(Lead.id).label("total_leads"),
                func.coalesce(func.sum(case((Lead.status == "Converted", 1), else_=0)), 0).label(
                    "converted_leads"
                ),
                func.coalesce(func.avg(Lead.score), 0.0).label("avg_score"),
            )
            .where(*filters)
            .group_by(Lead.source)
            .order_by(Lead.source.asc())
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Rep Leaderboard ---
    async def rep_leaderboard(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 100,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        filters = self._scoped(
            [Deal.organization_id == org_id, User.organization_id == org_id],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
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
            .where(*filters)
            .group_by(User.id, User.name, User.email, User.role)
            .order_by(
                func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)).desc(),
                # Unique tiebreakers keep ranks and the "Top Performer"
                # badge stable when revenues tie.
                User.name.asc(),
                User.id.asc(),
            )
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Revenue Forecasting ---
    async def revenue_forecast(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> Any | None:
        """Open-pipeline totals plus weighted pipeline; closed deals excluded."""
        filters = self._scoped(
            [Deal.organization_id == org_id, Deal.stage.not_in(OPEN_STAGES_EXCLUSION)],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = select(
            func.coalesce(func.sum(Deal.amount), 0.0).label("total_pipeline"),
            func.coalesce(func.sum(Deal.amount * (Deal.probability / 100.0)), 0.0).label(
                "weighted"
            ),
        ).where(*filters)
        res = await db.execute(query)
        return res.one_or_none()

    async def forecast_by_period(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> list[Any]:
        """Open pipeline grouped by quarter of each deal's expected close date."""
        quarter = func.date_trunc("quarter", Deal.expected_close_date)
        filters = self._scoped(
            [
                Deal.organization_id == org_id,
                Deal.stage.not_in(OPEN_STAGES_EXCLUSION),
                Deal.expected_close_date.is_not(None),
            ],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = (
            select(
                func.to_char(quarter, 'YYYY-"Q"Q').label("period"),
                func.count(Deal.id).label("deal_count"),
                func.coalesce(func.sum(Deal.amount), 0.0).label("pipeline_amount"),
                func.coalesce(func.sum(Deal.amount * (Deal.probability / 100.0)), 0.0).label(
                    "weighted_amount"
                ),
            )
            .where(*filters)
            .group_by(quarter)
            .order_by(quarter)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Activity Metrics ---
    async def count_calls(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        filters = self._scoped(
            [CallLog.organization_id == org_id],
            access,
            assigned=CallLog.created_by,
            created=CallLog.created_by,
        )
        res = await db.execute(
            select(func.count(CallLog.id)).where(*filters)
        )
        return res.scalar() or 0

    async def total_call_duration_seconds(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        filters = self._scoped(
            [CallLog.organization_id == org_id],
            access,
            assigned=CallLog.created_by,
            created=CallLog.created_by,
        )
        res = await db.execute(
            select(func.coalesce(func.sum(CallLog.duration_seconds), 0)).where(*filters)
        )
        return int(res.scalar() or 0)

    async def count_emails(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        filters = self._scoped(
            [Email.organization_id == org_id],
            access,
            assigned=Email.created_by,
            created=Email.created_by,
        )
        res = await db.execute(select(func.count(Email.id)).where(*filters))
        return res.scalar() or 0

    async def count_opened_emails(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        """Distinct logged emails that have at least one 'opened' tracking event."""
        filters = self._scoped(
            [Email.organization_id == org_id, EmailLog.event_type == "opened"],
            access,
            assigned=Email.created_by,
            created=Email.created_by,
        )
        res = await db.execute(
            select(func.count(func.distinct(EmailLog.email_id)))
            .join(Email, Email.id == EmailLog.email_id)
            .where(*filters)
        )
        return res.scalar() or 0

    async def count_meetings(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        filters = self._scoped(
            [Meeting.organization_id == org_id],
            access,
            assigned=Meeting.created_by,
            created=Meeting.created_by,
        )
        res = await db.execute(
            select(func.count(Meeting.id)).where(*filters)
        )
        return res.scalar() or 0

    # --- Deal Duration / CAC / LTV / Churn ---
    async def count_deals(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> int:
        filters = self._scoped(
            [Deal.organization_id == org_id],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        res = await db.execute(select(func.count(Deal.id)).where(*filters))
        return res.scalar() or 0

    async def won_aggregate(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> Any | None:
        filters = self._scoped(
            [Deal.organization_id == org_id, Deal.stage == CLOSED_WON_STAGE],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = select(
            func.count(Deal.id).label("won_cnt"),
            func.coalesce(func.sum(Deal.amount), 0.0).label("tot_rev"),
        ).where(*filters)
        res = await db.execute(query)
        return res.one_or_none()

    async def lost_aggregate(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> Any | None:
        filters = self._scoped(
            [Deal.organization_id == org_id, Deal.stage == CLOSED_LOST_STAGE],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        query = select(
            func.count(Deal.id).label("lost_cnt"),
            func.coalesce(func.sum(Deal.amount), 0.0).label("lost_arr"),
        ).where(*filters)
        res = await db.execute(query)
        return res.one_or_none()

    # --- Quota Attainment ---
    async def rep_quota(
        self,
        db: AsyncSession,
        org_id: str,
        limit: int = 100,
        access: RecordAccessContext | None = None,
    ) -> list[Any]:
        open_amount = case((Deal.stage.not_in(OPEN_STAGES_EXCLUSION), Deal.amount), else_=0.0)
        filters = self._scoped(
            [Deal.organization_id == org_id, User.organization_id == org_id],
            access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
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
            .where(*filters)
            .group_by(User.id, User.name, User.role)
            .order_by(User.name.asc(), User.id.asc())
            .limit(limit)
        )
        res = await db.execute(query)
        return list(res.all())

    # --- Financial overview ---
    async def financial_overview(
        self,
        db: AsyncSession,
        org_id: str,
        *,
        deal_access: RecordAccessContext | None = None,
        quote_access: RecordAccessContext | None = None,
        invoice_access: RecordAccessContext | None = None,
        payment_access: RecordAccessContext | None = None,
    ) -> dict[str, float | int]:
        """Return independently labelled operational and verified financial totals."""
        deal_filters = self._scoped(
            [Deal.organization_id == org_id],
            deal_access,
            assigned=Deal.assigned_to,
            created=Deal.created_by,
        )
        deal_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case((Deal.stage.not_in(OPEN_STAGES_EXCLUSION), Deal.amount), else_=0.0)
                    ),
                    0.0,
                ).label("pipeline_value"),
                func.coalesce(
                    func.sum(case((Deal.stage == CLOSED_WON_STAGE, Deal.amount), else_=0.0)),
                    0.0,
                ).label("booked_value"),
            ).where(*deal_filters)
        )
        deal_row = deal_result.one()

        quote_filters = self._scoped(
            [Quote.organization_id == org_id],
            quote_access,
            assigned=Quote.created_by,
            created=Quote.created_by,
        )
        quote_result = await db.execute(
            select(
                func.count(Quote.id).label("quote_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (Quote.status.in_(("Sent", "Accepted")), Quote.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("quoted_value"),
                func.coalesce(func.sum(Quote.total_amount), 0).label("total_quote_value"),
                func.coalesce(
                    func.sum(case((Quote.status == "Accepted", Quote.total_amount), else_=0)), 0
                ).label("accepted_quote_value"),
            ).where(*quote_filters)
        )
        quote_row = quote_result.one()

        outstanding = case(
            (
                Invoice.status.in_(("Finalized", "Accepted")),
                Invoice.amount - Invoice.paid_amount,
            ),
            else_=0,
        )
        overdue = case(
            (
                Invoice.status.in_(("Finalized", "Accepted")) & (Invoice.due_date < func.now()),
                Invoice.amount - Invoice.paid_amount,
            ),
            else_=0,
        )
        invoice_filters = self._scoped(
            [Invoice.organization_id == org_id],
            invoice_access,
            assigned=Invoice.created_by,
            created=Invoice.created_by,
        )
        invoice_result = await db.execute(
            select(
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.amount), 0).label("invoiced_value"),
                func.coalesce(func.sum(Invoice.paid_amount), 0).label("invoice_paid_value"),
                func.coalesce(func.sum(outstanding), 0).label("outstanding_amount"),
                func.coalesce(func.sum(overdue), 0).label("overdue_amount"),
            ).where(*invoice_filters)
        )
        invoice_row = invoice_result.one()

        payment_filters = self._scoped(
            [Payment.organization_id == org_id, Payment.status == "Succeeded"],
            payment_access,
            assigned=Payment.recorded_by,
            created=Payment.recorded_by,
        )
        payment_result = await db.execute(
            select(
                func.count(Payment.id).label("payment_count"),
                func.coalesce(func.sum(Payment.amount), 0).label("collected_revenue"),
            ).where(*payment_filters)
        )
        payment_row = payment_result.one()

        return {
            "pipeline_value": float(deal_row.pipeline_value or 0),
            "booked_value": float(deal_row.booked_value or 0),
            "quote_count": int(quote_row.quote_count or 0),
            "quoted_value": float(quote_row.quoted_value or 0),
            "total_quote_value": float(quote_row.total_quote_value or 0),
            "accepted_quote_value": float(quote_row.accepted_quote_value or 0),
            "invoice_count": int(invoice_row.invoice_count or 0),
            "invoiced_value": float(invoice_row.invoiced_value or 0),
            "invoice_paid_value": float(invoice_row.invoice_paid_value or 0),
            "outstanding_amount": float(invoice_row.outstanding_amount or 0),
            "overdue_amount": float(invoice_row.overdue_amount or 0),
            "payment_count": int(payment_row.payment_count or 0),
            "collected_revenue": float(payment_row.collected_revenue or 0),
        }

    async def invoice_status_breakdown(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> list[Any]:
        filters = self._scoped(
            [Invoice.organization_id == org_id],
            access,
            assigned=Invoice.created_by,
            created=Invoice.created_by,
        )
        result = await db.execute(
            select(
                Invoice.status,
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.amount), 0).label("invoice_value"),
                func.coalesce(func.sum(Invoice.paid_amount), 0).label("paid_value"),
            )
            .where(*filters)
            .group_by(Invoice.status)
            .order_by(Invoice.status.asc())
        )
        return list(result.all())

    async def quote_status_breakdown(
        self, db: AsyncSession, org_id: str, access: RecordAccessContext | None = None
    ) -> list[Any]:
        filters = self._scoped(
            [Quote.organization_id == org_id],
            access,
            assigned=Quote.created_by,
            created=Quote.created_by,
        )
        result = await db.execute(
            select(
                Quote.status,
                func.count(Quote.id).label("quote_count"),
                func.coalesce(func.sum(Quote.total_amount), 0).label("quote_value"),
            )
            .where(*filters)
            .group_by(Quote.status)
            .order_by(Quote.status.asc())
        )
        return list(result.all())

    async def quote_conversion_counts(
        self,
        db: AsyncSession,
        org_id: str,
        quote_access: RecordAccessContext | None = None,
        invoice_access: RecordAccessContext | None = None,
    ) -> tuple[int, int]:
        quote_filters = self._scoped(
            [Quote.organization_id == org_id],
            quote_access,
            assigned=Quote.created_by,
            created=Quote.created_by,
        )
        invoice_join_conditions = [
            Invoice.quote_id == Quote.id,
            Invoice.organization_id == org_id,
        ]
        invoice_filter = record_access_filter(
            invoice_access,
            assigned_column=Invoice.created_by,
            created_column=Invoice.created_by,
        )
        if invoice_filter is not None:
            invoice_join_conditions.append(invoice_filter)
        result = await db.execute(
            select(
                func.coalesce(func.sum(case((Quote.status == "Accepted", 1), else_=0)), 0).label(
                    "accepted_count"
                ),
                func.coalesce(
                    func.sum(
                        case(
                            ((Quote.status == "Accepted") & Invoice.id.is_not(None), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("invoiced_count"),
            )
            .select_from(Quote)
            .outerjoin(
                Invoice,
                and_(*invoice_join_conditions),
            )
            .where(*quote_filters)
        )
        row = result.one()
        return int(row.accepted_count or 0), int(row.invoiced_count or 0)

    # --- Custom Reports ---
    async def list_custom_reports(
        self,
        db: AsyncSession,
        org_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
    ) -> Sequence[CustomReport]:
        stmt = select(CustomReport).where(CustomReport.organization_id == org_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(CustomReport.name.ilike(term), CustomReport.filters.ilike(term)))
        stmt = (
            stmt
            .order_by(CustomReport.created_at.desc(), CustomReport.id.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_custom_reports(
        self, db: AsyncSession, org_id: str, *, search: str | None = None
    ) -> int:
        stmt = select(func.count()).select_from(CustomReport).where(
            CustomReport.organization_id == org_id
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(CustomReport.name.ilike(term), CustomReport.filters.ilike(term)))
        result = await db.execute(stmt)
        return int(result.scalar_one())

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
        self,
        db: AsyncSession,
        export_id: str,
        org_id: str,
        requested_by: str | None = None,
    ) -> ReportExport | None:
        filters = [
            ReportExport.id == export_id,
            ReportExport.organization_id == org_id,
        ]
        if requested_by is not None:
            filters.append(ReportExport.requested_by == requested_by)
        stmt = select(ReportExport).where(*filters)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    # --- Scheduled Reports ---
    async def create_scheduled_report(self, db: AsyncSession, *, data: dict) -> ScheduledReport:
        report = ScheduledReport(**data)
        db.add(report)
        return report

    async def list_scheduled_reports(
        self,
        db: AsyncSession,
        org_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        search: str | None = None,
    ) -> Sequence[ScheduledReport]:
        stmt = select(ScheduledReport).where(ScheduledReport.organization_id == org_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ScheduledReport.report_type.ilike(term),
                    ScheduledReport.email.ilike(term),
                    ScheduledReport.frequency.ilike(term),
                )
            )
        stmt = (
            stmt
            .order_by(ScheduledReport.created_at.desc(), ScheduledReport.id.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_scheduled_reports(
        self, db: AsyncSession, org_id: str, *, search: str | None = None
    ) -> int:
        stmt = select(func.count()).select_from(ScheduledReport).where(
            ScheduledReport.organization_id == org_id
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ScheduledReport.report_type.ilike(term),
                    ScheduledReport.email.ilike(term),
                    ScheduledReport.frequency.ilike(term),
                )
            )
        result = await db.execute(stmt)
        return int(result.scalar_one())

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
