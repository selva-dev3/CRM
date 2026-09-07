from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import normalize_currency_code_or_default
from app.core.locale import normalize_locale_or_default
from app.models import (
    CallLog,
    Deal,
    Email,
    Invoice,
    Lead,
    Meeting,
    Organization,
    Payment,
    Quote,
    Task,
    User,
)

CLOSED_WON_STAGE = "Closed Won"
CLOSED_LOST_STAGE = "Closed Lost"
CLOSED_DEAL_STAGES = (CLOSED_WON_STAGE, CLOSED_LOST_STAGE)
COMPLETED_TASK_STATUS = "Completed"
SENT_EMAIL_STATUS = "sent"


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

    async def financial_kpis(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        currency: str,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, float | int]:
        quote_filters = [
            Quote.organization_id == organization_id,
            func.upper(Quote.currency) == currency,
        ]
        invoice_filters = [
            Invoice.organization_id == organization_id,
            Invoice.status != "Cancelled",
            func.upper(Invoice.currency) == currency,
        ]
        if start_at is not None:
            quote_filters.append(Quote.created_at >= start_at)
            invoice_filters.append(Invoice.created_at >= start_at)
        if end_at is not None:
            quote_filters.append(Quote.created_at < end_at)
            invoice_filters.append(Invoice.created_at < end_at)
        quote_row = (
            await db.execute(
                select(
                    func.count(Quote.id),
                    func.coalesce(func.sum(Quote.total_amount), 0),
                    func.coalesce(func.sum(case((Quote.status == "Accepted", 1), else_=0)), 0),
                    func.coalesce(
                        func.sum(
                            case(
                                (Quote.status.in_(("Sent", "Accepted", "Rejected")), 1),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(*quote_filters)
            )
        ).one()

        paid = (
            select(
                Payment.invoice_id.label("invoice_id"),
                func.sum(Payment.amount).label("paid_amount"),
            )
            .where(
                Payment.organization_id == organization_id,
                Payment.status == "Succeeded",
            )
            .group_by(Payment.invoice_id)
            .subquery()
        )
        paid_amount = func.coalesce(paid.c.paid_amount, 0)
        invoice_row = (
            await db.execute(
                select(
                    func.count(Invoice.id),
                    func.coalesce(func.sum(Invoice.amount), 0),
                    func.coalesce(func.sum(paid_amount), 0),
                    func.coalesce(
                        func.sum(
                            case(
                                (Invoice.amount > paid_amount, Invoice.amount - paid_amount),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    and_(Invoice.status == "Accepted", paid_amount <= 0),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    and_(
                                        Invoice.status == "Accepted",
                                        paid_amount > 0,
                                        paid_amount < Invoice.amount,
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((paid_amount >= Invoice.amount, 1), else_=0)),
                        0,
                    ),
                )
                .outerjoin(paid, paid.c.invoice_id == Invoice.id)
                .where(*invoice_filters)
            )
        ).one()
        delivered_quotes = int(quote_row[3] or 0)
        accepted_quotes = int(quote_row[2] or 0)
        invoice_total = float(invoice_row[1] or 0)
        collected = float(invoice_row[2] or 0)
        return {
            "quote_count": int(quote_row[0] or 0),
            "quote_value": float(quote_row[1] or 0),
            "quote_conversion_percentage": round(
                accepted_quotes / delivered_quotes * 100, 2
            )
            if delivered_quotes
            else 0.0,
            "invoice_count": int(invoice_row[0] or 0),
            "invoice_total": invoice_total,
            "paid_amount": collected,
            "outstanding_amount": float(invoice_row[3] or 0),
            "pending_payment_count": int(invoice_row[4] or 0),
            "partially_paid_invoice_count": int(invoice_row[5] or 0),
            "paid_invoice_count": int(invoice_row[6] or 0),
            "revenue": collected,
            "collection_rate_percentage": round(collected / invoice_total * 100, 2)
            if invoice_total
            else 0.0,
        }

    async def sum_pipeline_deals(self, db: AsyncSession, organization_id: str) -> float:
        result = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(CLOSED_DEAL_STAGES),
            )
        )
        return float(result.scalar() or 0.0)

    async def sum_won_deals(self, db: AsyncSession, organization_id: str) -> float:
        result = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage == CLOSED_WON_STAGE,
            )
        )
        return float(result.scalar() or 0.0)

    async def count_closed_deals(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Deal.id)).where(
                Deal.organization_id == organization_id,
                Deal.stage.in_(CLOSED_DEAL_STAGES),
            )
        )
        return result.scalar() or 0

    async def count_won_deals(self, db: AsyncSession, organization_id: str) -> int:
        result = await db.execute(
            select(func.count(Deal.id)).where(
                Deal.organization_id == organization_id,
                Deal.stage == CLOSED_WON_STAGE,
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
            .where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
            )
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
        return [row._tuple() for row in result.all()]

    async def top_performers(
        self, db: AsyncSession, organization_id: str, limit: int = 5
    ) -> list[tuple]:
        result = await db.execute(
            select(User.name, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
            .join(
                User,
                and_(
                    Deal.assigned_to == User.id,
                    User.organization_id == organization_id,
                ),
            )
            .where(
                Deal.organization_id == organization_id,
                Deal.assigned_to.isnot(None),
                Deal.stage == CLOSED_WON_STAGE,
            )
            .group_by(User.id, User.name)
            .order_by(func.sum(Deal.amount).desc())
            .limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def lead_source_conversions(self, db: AsyncSession, organization_id: str) -> list[tuple]:
        converted = case(
            (
                Lead.status.ilike("%convert%") | Lead.status.ilike("%won%"),
                1,
            ),
            else_=0,
        )
        result = await db.execute(
            select(
                Lead.source,
                func.count(Lead.id),
                func.coalesce(func.sum(converted), 0),
            )
            .where(
                Lead.organization_id == organization_id,
                Lead.is_archived.is_(False),
            )
            .group_by(Lead.source)
        )
        return [row._tuple() for row in result.all()]

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
                Email.status.ilike(SENT_EMAIL_STATUS),
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
                Task.status == COMPLETED_TASK_STATUS,
                Task.updated_at >= start,
                Task.updated_at < end,
            )
        )
        return result.scalar() or 0

    async def recent_deals(
        self, db: AsyncSession, organization_id: str, limit: int = 5
    ) -> list[tuple[Deal, str | None]]:
        result = await db.execute(
            select(Deal, User.name)
            .outerjoin(
                User,
                and_(
                    Deal.assigned_to == User.id,
                    User.organization_id == organization_id,
                    User.is_active.is_(True),
                ),
            )
            .where(Deal.organization_id == organization_id)
            .order_by(Deal.updated_at.desc())
            .limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def count_deals_and_sum(
        self, db: AsyncSession, organization_id: str
    ) -> tuple[int, float]:
        result = await db.execute(
            select(func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(CLOSED_DEAL_STAGES),
            )
        )
        row = result.first()
        return (row[0] if row else 0, float(row[1]) if row else 0.0)

    async def top_deal(self, db: AsyncSession, organization_id: str) -> Deal | None:
        result = await db.execute(
            select(Deal)
            .where(
                Deal.organization_id == organization_id,
                Deal.stage.notin_(CLOSED_DEAL_STAGES),
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

    async def get_organization_currency_locale(
        self, db: AsyncSession, organization_id: str
    ) -> tuple[str, str]:
        result = await db.execute(
            select(Organization.currency, Organization.language).where(
                Organization.id == organization_id
            )
        )
        row = result.first()
        if not row:
            return "INR", "en"
        currency = normalize_currency_code_or_default(row[0])
        locale = normalize_locale_or_default(row[1])
        return currency, locale
