import asyncio
import calendar as py_cal
import csv
import io
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.report_repository import (
    CLOSED_LOST_STAGE,
    CLOSED_WON_STAGE,
    ReportRepository,
)
from app.schemas.report_schemas import ReportTypeEnum
from app.services.s3_service import s3_service

logger = get_logger(__name__)

_SECONDS_PER_DAY = 86400.0

_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
_CSV_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+$")
VALID_FREQUENCIES = {"Daily", "Weekly", "Monthly"}
VALID_REPORT_TYPES = {e.value for e in ReportTypeEnum}

# Maps each exportable report type to the service method that computes it,
# so PDF/CSV exports always reflect the requested report's live data.
_REPORT_GETTERS = {
    ReportTypeEnum.SALES_PERFORMANCE.value: "get_sales_performance_report",
    ReportTypeEnum.PIPELINE_VELOCITY.value: "get_pipeline_velocity_report",
    ReportTypeEnum.WIN_LOSS_RATIO.value: "get_win_loss_report",
    ReportTypeEnum.LEAD_ATTRIBUTION.value: "get_lead_attribution_report",
    ReportTypeEnum.REP_LEADERBOARD.value: "get_rep_leaderboard_report",
    ReportTypeEnum.REVENUE_FORECASTING.value: "get_revenue_forecasting_report",
    ReportTypeEnum.ACTIVITY_METRICS.value: "get_activity_metrics_report",
    ReportTypeEnum.DEAL_DURATION.value: "get_deal_duration_report",
    ReportTypeEnum.CUSTOMER_ACQUISITION_COST.value: "get_cac_report",
    ReportTypeEnum.CUSTOMER_LIFETIME_VALUE.value: "get_ltv_report",
    ReportTypeEnum.CHURN_ANALYSIS.value: "get_churn_analysis_report",
    ReportTypeEnum.QUOTA_ATTAINMENT.value: "get_quota_attainment_report",
    ReportTypeEnum.FINANCIAL_OVERVIEW.value: "get_financial_overview_report",
    ReportTypeEnum.QUOTE_CONVERSION.value: "get_quote_conversion_report",
}


def _normalize_report_type(report_type: Any) -> str:
    """Accept ReportTypeEnum or its serialized value and return the canonical string."""
    if isinstance(report_type, ReportTypeEnum):
        return report_type.value
    return str(report_type) if report_type is not None else ""


def _build_export_object_key(org_id: str, file_format: str) -> str:
    """Build a unique, tenant-scoped object key for a report export."""
    safe_org = re.sub(r"[^A-Za-z0-9_-]", "_", str(org_id or "unknown"))[:64]
    return f"exports/{safe_org}/{uuid.uuid4().hex}.{file_format}"


def today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def _cleanup_export_object(s3_key: str) -> None:
    """Best-effort cleanup when export metadata cannot be committed."""
    try:
        await asyncio.to_thread(s3_service.delete_file, s3_key)
    except Exception:
        logger.exception("Failed to clean up orphaned report export object key=%s", s3_key)


def compute_next_run(frequency: str, start_dt: datetime | None = None) -> datetime:
    base = start_dt or datetime.now(UTC)
    clean_freq = (frequency or "").capitalize()
    if clean_freq == "Daily":
        return base + timedelta(days=1)
    if clean_freq == "Monthly":
        year = base.year + (base.month // 12)
        month = (base.month % 12) + 1
        max_days = py_cal.monthrange(year, month)[1]
        clamped_day = min(base.day, max_days)
        return base.replace(year=year, month=month, day=clamped_day)
    return base + timedelta(days=7)


def _generate_pdf_bytes(title: str, lines: list[str]) -> bytes:
    """Generate a standard valid minimal PDF-1.4 binary document."""
    escaped_title = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_content = f"BT\n/F1 16 Tf\n50 750 Td\n({escaped_title}) Tj\n/F1 10 Tf\n0 -25 Td\n"
    for line in lines:
        sanitized = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_content += f"({sanitized}) Tj\n0 -15 Td\n"
    stream_content += "ET"
    stream_bytes = stream_content.encode("latin-1", "replace")
    stream_len = len(stream_bytes)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(stream_len).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    header = b"%PDF-1.4\n"
    pos1 = len(header)
    pos2 = pos1 + len(obj1)
    pos3 = pos2 + len(obj2)
    pos4 = pos3 + len(obj3)
    pos5 = pos4 + len(obj4)
    xref_pos = pos5 + len(obj5)

    xref = (
        f"xref\n0 6\n0000000000 65535 f \n"
        f"{pos1:010d} 00000 n \n"
        f"{pos2:010d} 00000 n \n"
        f"{pos3:010d} 00000 n \n"
        f"{pos4:010d} 00000 n \n"
        f"{pos5:010d} 00000 n \n"
    ).encode("ascii")
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    return header + obj1 + obj2 + obj3 + obj4 + obj5 + xref + trailer


class ReportService:
    """Business logic for analytics reports with strict multi-tenant organization isolation."""

    def __init__(self, repository: ReportRepository | None = None) -> None:
        self.repository = repository or ReportRepository()

    async def _resolve_org_id(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> str:
        """Resolve organization strictly from the authenticated user.

        Never falls back to selecting an arbitrary organization from the
        database.  If an explicit *org_id* is supplied by the caller it
        must match the authenticated user's organization.

        ``internal=True`` is reserved for trusted background jobs (e.g. the
        scheduled-report Celery task) which carry no request user; it still
        requires an explicit *org_id* and never widens API-facing access.
        """
        user_org = (
            current_user.organization_id
            if current_user and getattr(current_user, "organization_id", None)
            else None
        )

        if not user_org:
            if internal and org_id and org_id.strip():
                return org_id.strip()
            raise ForbiddenError(
                message="Organization context is required. Please ensure your account is associated with an organization.",
            )

        # If the caller also passed an explicit org_id, verify it matches.
        if org_id and org_id.strip() and org_id.strip() != user_org:
            raise ForbiddenError(
                message="You do not have access to the requested organization.",
            )

        return user_org

    async def get_sales_performance_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        total_rev = await self.repository.total_won_revenue(db, target_org)
        rows = await self.repository.rep_performance(db, target_org)
        quotas = await self.repository.quotas_by_user(db, target_org)

        table_rows = []
        for user_id, name, role, assigned, closed, rev in rows:
            rev_val = float(rev or 0.0)
            closed_val = int(closed or 0)
            assigned_val = int(assigned or 0)
            win_rate = round((closed_val / assigned_val * 100.0), 1) if assigned_val > 0 else 0.0
            quota = quotas.get(user_id)
            attainment = round((rev_val / quota * 100.0), 1) if quota else None
            avg_deal_size = round(rev_val / closed_val, 2) if closed_val > 0 else 0.0
            table_rows.append(
                {
                    "rep_name": name,
                    "role": role or "Sales Executive",
                    "deals_assigned": assigned_val,
                    "deals_closed": closed_val,
                    "revenue": round(rev_val, 2),
                    "win_rate": win_rate,
                    "quota_target": quota,
                    "attainment_pct": attainment,
                    "avg_deal_size": avg_deal_size,
                }
            )

        monthly_target = sum(quotas.values())
        return {
            "report_type": "Sales Performance",
            "metrics": {
                "total_revenue": round(total_rev, 2),
                "monthly_target": round(monthly_target, 2),
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_pipeline_velocity_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        rows = await self.repository.stage_age_breakdown(db, target_org)
        cycle = await self.repository.closed_cycle_stats(db, target_org)

        table_rows = []
        for stage_name, cnt, val, avg_age_sec in rows:
            cnt_val = int(cnt or 0)
            val_amount = float(val or 0.0)
            # Real age of deals currently sitting in the stage.
            avg_days = round(float(avg_age_sec or 0.0) / _SECONDS_PER_DAY, 1)
            risk = "Low" if avg_days < 5.0 else ("Medium" if avg_days < 10.0 else "High")
            table_rows.append(
                {
                    "stage": stage_name,
                    "deal_count": cnt_val,
                    "total_value": round(val_amount, 2),
                    "avg_days_in_stage": avg_days,
                    "bottleneck_risk": risk,
                }
            )

        closed_won_cnt = int(cycle.closed_cnt if cycle else 0)
        avg_days_to_close = (
            round(float(cycle.avg_sec or 0.0) / _SECONDS_PER_DAY, 1)
            if cycle and closed_won_cnt > 0
            else 0.0
        )
        return {
            "report_type": "Pipeline Velocity",
            "metrics": {
                "avg_days_to_close": avg_days_to_close,
                "closed_won_deals": closed_won_cnt,
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_win_loss_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        won_count = await self.repository.count_deals_in_stage(db, target_org, CLOSED_WON_STAGE)
        lost_count = await self.repository.count_deals_in_stage(db, target_org, CLOSED_LOST_STAGE)
        total_closed = won_count + lost_count
        overall_win_pct = round((won_count / total_closed * 100.0), 1) if total_closed > 0 else 0.0
        overall_loss_pct = round(100.0 - overall_win_pct, 1) if total_closed > 0 else 0.0

        rows = await self.repository.win_loss_by_industry(db, target_org)
        top_loss_reason = await self.repository.top_loss_reason(db, target_org)

        # Modal loss reason per industry so each segment reports only reasons
        # actually recorded against its own deals (never the org-wide mode).
        reason_rows = await self.repository.loss_reason_by_industry(db, target_org)
        industry_reason_counts: dict[str, tuple[str, int]] = {}
        for ind, reason, cnt in reason_rows:
            key = ind or "General Enterprise"
            c = int(cnt or 0)
            if key not in industry_reason_counts or c > industry_reason_counts[key][1]:
                industry_reason_counts[key] = (str(reason), c)

        table_rows = []
        for ind, won, lost, won_v, lost_v in rows:
            w_cnt = int(won or 0)
            l_cnt = int(lost or 0)
            tot_cnt = w_cnt + l_cnt
            win_pct = round((w_cnt / tot_cnt * 100.0), 1) if tot_cnt > 0 else 0.0
            ind_label = ind or "General Enterprise"
            table_rows.append(
                {
                    "segment": ind_label,
                    "won_deals": w_cnt,
                    "lost_deals": l_cnt,
                    "total_deals": tot_cnt,
                    "win_percentage": win_pct,
                    "won_value": round(float(won_v or 0.0), 2),
                    "lost_value": round(float(lost_v or 0.0), 2),
                    "primary_loss_reason": industry_reason_counts.get(ind_label, (None, 0))[0],
                }
            )

        return {
            "report_type": "Win Loss Analysis",
            "metrics": {
                "win_percentage": overall_win_pct,
                "loss_percentage": overall_loss_pct,
                "total_won_deals": won_count,
                "total_lost_deals": lost_count,
                "top_loss_reason": top_loss_reason,
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_lead_attribution_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        rows = await self.repository.leads_by_source(db, target_org)

        table_rows = []
        for src, total_l, conv_l, avg_s in rows:
            tot = int(total_l or 0)
            conv = int(conv_l or 0)
            conv_rate = round((conv / tot * 100.0), 1) if tot > 0 else 0.0
            table_rows.append(
                {
                    "source": src or "Direct Web",
                    "total_leads": tot,
                    "converted_leads": conv,
                    "conversion_rate": conv_rate,
                    "avg_lead_score": round(float(avg_s or 0.0), 1),
                }
            )

        return {
            "report_type": "Lead Attribution",
            "metrics": {"table_rows": table_rows},
            "generated_at": today_str(),
        }

    async def get_rep_leaderboard_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        rows = await self.repository.rep_leaderboard(db, target_org)
        quotas = await self.repository.quotas_by_user(db, target_org)

        table_rows = []
        for idx, (user_id, name, email, role, deals, rev) in enumerate(rows, start=1):
            rev_val = float(rev or 0.0)
            deals_val = int(deals or 0)
            quota = quotas.get(user_id)
            quota_pct = round((rev_val / quota) * 100.0, 1) if quota else None
            if idx == 1 and rev_val > 0:
                badge = "Top Performer"
            elif quota_pct is not None and quota_pct >= 100.0:
                badge = "Quota Met"
            else:
                badge = "In Progress"
            table_rows.append(
                {
                    "rank": idx,
                    "name": name,
                    "email": email,
                    "role": role or "Sales Representative",
                    "deals_closed": deals_val,
                    "revenue": round(rev_val, 2),
                    "quota_target": quota,
                    "attainment_pct": quota_pct,
                    "badge": badge,
                }
            )

        return {
            "report_type": "Rep Leaderboard",
            "metrics": {"top_reps": table_rows, "table_rows": table_rows},
            "generated_at": today_str(),
        }

    async def get_revenue_forecasting_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        committed_rev = await self.repository.total_won_revenue(db, target_org)
        row = await self.repository.revenue_forecast(db, target_org)
        pipeline_total = float(row.total_pipeline if row else 0.0)
        weighted_pipeline = float(row.weighted if row else 0.0)

        period_rows = await self.repository.forecast_by_period(db, target_org)
        table_rows = [
            {
                "period": period,
                "open_deals": int(cnt or 0),
                "pipeline_amount": round(float(pipeline or 0.0), 2),
                "pipeline_weighted": round(float(weighted or 0.0), 2),
            }
            for period, cnt, pipeline, weighted in period_rows
        ]

        return {
            "report_type": "Revenue Forecast",
            "metrics": {
                "committed_revenue": round(committed_rev, 2),
                "open_pipeline_amount": round(pipeline_total, 2),
                "weighted_pipeline_amount": round(weighted_pipeline, 2),
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_activity_metrics_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        total_calls = await self.repository.count_calls(db, target_org)
        call_duration_sec = await self.repository.total_call_duration_seconds(db, target_org)
        total_emails = await self.repository.count_emails(db, target_org)
        opened_emails = await self.repository.count_opened_emails(db, target_org)
        total_meetings = await self.repository.count_meetings(db, target_org)

        email_open_rate = (
            round(opened_emails / total_emails * 100.0, 1) if total_emails > 0 else 0.0
        )
        # CallLog / Meeting / Email rows carry no user attribution columns in the
        # current schema, so a per-rep breakdown would be fabricated; the report
        # therefore returns organization-level totals only.
        return {
            "report_type": "Activity Metrics",
            "metrics": {
                "total_calls": total_calls,
                "total_call_duration_minutes": round(call_duration_sec / 60.0, 1),
                "total_emails": total_emails,
                "opened_emails": opened_emails,
                "email_open_rate_pct": email_open_rate,
                "total_meetings": total_meetings,
                "table_rows": [],
            },
            "generated_at": today_str(),
        }

    async def get_deal_duration_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        cycle = await self.repository.closed_cycle_stats(db, target_org)
        stage_rows = await self.repository.stage_age_breakdown(db, target_org)

        closed_won_cnt = int(cycle.closed_cnt if cycle else 0)
        avg_sec = float(cycle.avg_sec or 0.0) if cycle else 0.0
        fastest_sec = float(cycle.fastest_sec or 0.0) if cycle else 0.0
        longest_sec = float(cycle.longest_sec or 0.0) if cycle else 0.0
        avg_cycle_days = round(avg_sec / _SECONDS_PER_DAY, 1) if closed_won_cnt > 0 else 0.0
        fastest_days = round(fastest_sec / _SECONDS_PER_DAY, 1) if closed_won_cnt > 0 else 0.0
        longest_days = round(longest_sec / _SECONDS_PER_DAY, 1) if closed_won_cnt > 0 else 0.0

        # Real bottleneck: the open stage whose current deals have the highest average age.
        primary_bottleneck = None
        slowest_days = -1.0
        for stage_name, _cnt, _val, avg_age_sec in stage_rows:
            avg_days = float(avg_age_sec or 0.0) / _SECONDS_PER_DAY
            if avg_days > slowest_days:
                slowest_days = avg_days
                primary_bottleneck = (
                    f"{stage_name} (avg {round(avg_days, 1)}d)" if stage_name else None
                )

        table_rows = []
        if closed_won_cnt > 0:
            table_rows.append(
                {
                    "deal_tier": "Closed Won Deals",
                    "deal_count": closed_won_cnt,
                    "avg_cycle_days": avg_cycle_days,
                    "fastest_close_days": fastest_days,
                    "longest_close_days": longest_days,
                    "primary_bottleneck": primary_bottleneck,
                }
            )

        return {
            "report_type": "Deal Duration",
            "metrics": {
                "avg_cycle_days": avg_cycle_days,
                "fastest_close_days": fastest_days,
                "longest_close_days": longest_days,
                "closed_won_deals": closed_won_cnt,
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_cac_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        await self._resolve_org_id(db, org_id, current_user, internal=internal)

        return {
            "report_type": "Customer Acquisition Cost",
            "metrics": {
                "available": False,
                "reason": (
                    "Customer acquisition cost is unavailable because marketing and sales "
                    "spend is not captured by this CRM."
                ),
                "table_rows": [],
            },
            "generated_at": today_str(),
        }

    async def get_ltv_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        await self._resolve_org_id(db, org_id, current_user, internal=internal)

        return {
            "report_type": "Customer Lifetime Value",
            "metrics": {
                "available": False,
                "reason": (
                    "Customer lifetime value is unavailable because customer-level verified "
                    "payment history and retention periods are not captured."
                ),
                "table_rows": [],
            },
            "generated_at": today_str(),
        }

    async def get_churn_analysis_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        await self._resolve_org_id(db, org_id, current_user, internal=internal)

        return {
            "report_type": "Churn Analysis",
            "metrics": {
                "available": False,
                "reason": (
                    "Customer churn is unavailable because customer subscriptions, renewals, "
                    "and cancellation events are not captured. Closed Lost deals are not churn."
                ),
                "table_rows": [],
            },
            "generated_at": today_str(),
        }

    async def get_quota_attainment_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        rows = await self.repository.rep_quota(db, target_org)
        quotas = await self.repository.quotas_by_user(db, target_org)

        table_rows = []
        total_rev_with_quota = 0.0
        total_target = 0.0
        for user_id, name, role, rev, pipe in rows:
            rev_val = float(rev or 0.0)
            pipe_val = float(pipe or 0.0)
            quota = quotas.get(user_id)
            attainment = round((rev_val / quota * 100.0), 1) if quota else None
            if quota and attainment is not None:
                status_lbl = (
                    "Target Met"
                    if attainment >= 100.0
                    else ("On Track" if attainment >= 80.0 else "At Risk")
                )
                total_rev_with_quota += rev_val
                total_target += quota
            else:
                status_lbl = "No Quota Set"
            table_rows.append(
                {
                    "rep_name": name,
                    "role": role or "Sales Executive",
                    "assigned_quota": quota,
                    "closed_revenue": round(rev_val, 2),
                    "pipeline_coverage": round(pipe_val, 2),
                    "attainment_pct": attainment,
                    "status": status_lbl,
                }
            )

        team_attainment = (
            round((total_rev_with_quota / total_target * 100.0), 1) if total_target > 0 else 0.0
        )
        return {
            "report_type": "Quota Attainment",
            "metrics": {
                "team_attainment_pct": team_attainment,
                "reps_with_quota": sum(1 for r in table_rows if r["assigned_quota"] is not None),
                "table_rows": table_rows,
            },
            "generated_at": today_str(),
        }

    async def get_financial_overview_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        totals = await self.repository.financial_overview(db, target_org)
        invoice_rows = await self.repository.invoice_status_breakdown(db, target_org)
        currency = await self.repository.organization_currency(db, target_org)
        return {
            "report_type": "Financial Overview",
            "metrics": {
                **{
                    key: round(value, 2) if isinstance(value, float) else value
                    for key, value in totals.items()
                },
                "currency": currency,
                "table_rows": [
                    {
                        "status": row.status or "Unknown",
                        "invoice_count": int(row.invoice_count or 0),
                        "invoice_value": round(float(row.invoice_value or 0), 2),
                        "paid_value": round(float(row.paid_value or 0), 2),
                        "outstanding_amount": round(
                            max(float(row.invoice_value or 0) - float(row.paid_value or 0), 0), 2
                        ),
                    }
                    for row in invoice_rows
                ],
            },
            "generated_at": today_str(),
        }

    async def get_quote_conversion_report(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        internal: bool = False,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user, internal=internal)
        rows = await self.repository.quote_status_breakdown(db, target_org)
        currency = await self.repository.organization_currency(db, target_org)
        accepted_count, invoiced_count = await self.repository.quote_conversion_counts(
            db, target_org
        )
        total_quotes = sum(int(row.quote_count or 0) for row in rows)
        return {
            "report_type": "Quote Conversion",
            "metrics": {
                "total_quotes": total_quotes,
                "accepted_quotes": accepted_count,
                "invoiced_quotes": invoiced_count,
                "quote_acceptance_rate": (
                    round(accepted_count / total_quotes * 100.0, 1) if total_quotes else 0.0
                ),
                "quote_to_invoice_rate": (
                    round(invoiced_count / accepted_count * 100.0, 1) if accepted_count else 0.0
                ),
                "currency": currency,
                "table_rows": [
                    {
                        "status": row.status or "Unknown",
                        "quote_count": int(row.quote_count or 0),
                        "quote_value": round(float(row.quote_value or 0), 2),
                    }
                    for row in rows
                ],
            },
            "generated_at": today_str(),
        }

    async def list_custom_reports(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        target_org = await self._resolve_org_id(db, org_id, current_user)
        reports = await self.repository.list_custom_reports(
            db, target_org, limit=limit, offset=offset
        )
        return [
            {
                "id": r.id,
                "name": r.name,
                "filters": r.filters or "All Accounts",
                "metrics_included": (r.metrics_included.split(",") if r.metrics_included else []),
                "created_at": r.created_at.strftime("%Y-%m-%d") if r.created_at else today_str(),  # type: ignore[attr-defined]
            }
            for r in reports
        ]

    async def create_custom_report(
        self,
        db: AsyncSession,
        name: str,
        filters: str | None = None,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        clean_name = (name or "").strip()
        if not clean_name:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Report name must not be empty.",
            )

        target_org = await self._resolve_org_id(db, org_id, current_user)
        await self.repository.create_custom_report(
            db,
            data={
                "organization_id": target_org,
                "name": clean_name,
                "filters": filters or "All Accounts",
                "metrics_included": "sales-performance,deal-duration,win-loss-ratio",
            },
        )
        await self._commit(db, "Failed to create custom report")
        return {
            "message": f"Custom report query '{clean_name}' saved successfully",
            "status": "success",
        }

    async def run_custom_report(
        self,
        db: AsyncSession,
        report_id: str,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user)
        report = await self.repository.get_custom_report(db, report_id, target_org)
        if not report:
            raise NotFoundError(message=f"Custom report with id '{report_id}' not found.")

        total_rev = await self.repository.total_won_revenue(db, target_org)
        deals_count = await self.repository.count_deals(db, target_org)

        raw_metrics = getattr(report, "metrics_included", None)
        metrics_included = raw_metrics.split(",") if raw_metrics else []
        filter_text = getattr(report, "filters", None) or "All Accounts"

        metrics: dict[str, Any] = {
            "total_revenue": total_rev,
            "deals_analyzed": deals_count,
            "filters_applied": filter_text,
            "metrics_included": metrics_included,
        }

        if "pipeline-velocity" in metrics_included or "pipeline" in filter_text.lower():
            velocity = await self.get_pipeline_velocity_report(db, target_org, current_user)
            metrics["pipeline_velocity"] = velocity.get("metrics", {})

        if "win-loss-ratio" in metrics_included or "win" in filter_text.lower():
            win_loss = await self.get_win_loss_report(db, target_org, current_user)
            metrics["win_loss"] = win_loss.get("metrics", {})

        return {
            "report_type": report.name,
            "metrics": metrics,
            "generated_at": today_str(),
        }

    async def delete_custom_report(
        self,
        db: AsyncSession,
        report_id: str,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user)
        report = await self.repository.get_custom_report(db, report_id, target_org)
        if not report:
            raise NotFoundError(message=f"Custom report with id '{report_id}' not found.")

        await self.repository.delete_custom_report(db, report)
        await self._commit(db, "Failed to delete custom report")
        return {"message": f"Custom report {report_id} deleted successfully", "status": "success"}

    async def _build_report_payload(
        self,
        db: AsyncSession,
        report_type_value: str,
        current_user: User | None,
        target_org: str | None = None,
    ) -> dict:
        """Run the real report for the requested type so exports contain its data.

        ``target_org`` is used only by trusted background callers (scheduler)
        that have no request user; interactive exports resolve the org from
        ``current_user`` as usual.
        """
        getter_name = _REPORT_GETTERS.get(report_type_value)
        if not getter_name:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"No report implementation registered for '{report_type_value}'.",
            )
        if target_org:
            return await getattr(self, getter_name)(db, target_org, None, internal=True)
        return await getattr(self, getter_name)(db, current_user=current_user)

    @staticmethod
    def _flatten_metrics(metrics: dict, max_lines: int = 20) -> list[str]:
        lines = []
        for key, value in metrics.items():
            if isinstance(value, (list, dict)):
                continue
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
            if len(lines) >= max_lines:
                break
        return lines

    async def export_report_pdf(
        self,
        db: AsyncSession,
        report_type: Any = ReportTypeEnum.SALES_PERFORMANCE,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        report_type_value = _normalize_report_type(report_type)
        if report_type_value not in VALID_REPORT_TYPES:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid report type '{report_type_value}'. Valid types: {sorted(VALID_REPORT_TYPES)}",
            )

        target_org = await self._resolve_org_id(db, org_id, current_user)
        requesting_user_id = (
            current_user.id if current_user and getattr(current_user, "id", None) else None
        )
        if not requesting_user_id:
            raise ForbiddenError(
                message="Authenticated user is required to export reports.",
            )

        # Generate actual PDF content from the requested report's live data.
        payload = await self._build_report_payload(db, report_type_value, current_user)
        metrics = payload.get("metrics", {})
        rows = metrics.get("table_rows") or []
        summary_lines = [
            f"Generated At: {today_str()}",
            *self._flatten_metrics(metrics),
            "",
            "Detail Rows:" if rows else "No detail rows available for this report.",
        ]
        for row in rows[:15]:
            summary_lines.append(" - " + ", ".join(f"{k}: {v}" for k, v in row.items()))

        pdf_bytes = _generate_pdf_bytes(
            title=f"{report_type_value.replace('-', ' ').title()} Report",
            lines=summary_lines,
        )

        object_name = _build_export_object_key(target_org, "pdf")
        try:
            file_obj = io.BytesIO(pdf_bytes)
            s3_key = await asyncio.to_thread(
                s3_service.upload_file,
                file_obj,
                object_name=object_name,
                content_type="application/pdf",
            )
            pdf_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
        except Exception as e:
            logger.exception(
                "S3 upload failed for PDF export org=%s report=%s", target_org, report_type_value
            )
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to upload PDF to storage. Please try again later.",
            ) from e

        try:
            export = await self.repository.create_export(
                db,
                data={
                    "organization_id": target_org,
                    "report_type": report_type_value,
                    "file_format": "pdf",
                    "download_url": None,
                    "s3_key": s3_key,
                    "requested_by": requesting_user_id,
                },
            )
            await self._commit(db, "Failed to record PDF export")
            await db.refresh(export)
            return {"pdf_url": pdf_url, "export_id": export.id}
        except Exception as e:
            await db.rollback()
            await _cleanup_export_object(s3_key)
            if isinstance(e, APIException):
                raise
            logger.exception(
                "Failed to record PDF export for org=%s report=%s", target_org, report_type_value
            )
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to start PDF export. Please try again later.",
            ) from e

    async def get_export_download(
        self,
        db: AsyncSession,
        export_id: str,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        """Mint a fresh presigned URL for a previously generated export."""
        target_org = await self._resolve_org_id(db, org_id, current_user)
        export = await self.repository.get_export(db, export_id, target_org)
        if not export:
            raise NotFoundError(message=f"Export '{export_id}' not found")

        s3_key = getattr(export, "s3_key", None)
        if not s3_key:
            logger.warning(
                "Export %s for org=%s has no s3_key; refusing to return expired legacy URL",
                export_id,
                target_org,
            )
            raise APIException(
                status_code=status.HTTP_410_GONE,
                message="This export is no longer available. Please regenerate the report.",
            )

        try:
            url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
        except Exception as e:
            logger.exception("Failed to generate presigned download URL for export %s", export_id)
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to generate download link. Please try again later.",
            ) from e

        return {"download_url": url, "expires_in": 3600}

    @staticmethod
    def _sanitize_csv_cell(value: Any) -> str:
        """Prevent CSV formula injection while preserving legitimate numeric negatives.

        Values starting with =, +, @ are always treated as dangerous.
        Values starting with - are escaped UNLESS the entire value parses as
        a numeric literal (e.g. ``-123``, ``-123.45``), which must remain a
        number so spreadsheets interpret it as numeric rather than text.
        """
        s = str(value) if value is not None else ""
        if not s:
            return s
        first = s[0]
        if first in ("=", "+", "@"):
            return "'" + s
        if first == "-":
            if _CSV_NUMERIC_RE.match(s):
                return s
            return "'" + s
        return s

    @staticmethod
    def _rows_to_csv(report_type_value: str, rows: list[dict]) -> str:
        """Serialize report rows to CSV with formula-injection escaping.

        Uses the standard library writer for proper quoting/escaping.
        """
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
        header: list[str] = []
        for row in rows:
            for key in row:
                if key not in header:
                    header.append(key)
        if header:
            writer.writerow(header)
            for row in rows:
                writer.writerow([ReportService._sanitize_csv_cell(row.get(col)) for col in header])
        else:
            writer.writerow(["Report Type", "Generated At"])
            writer.writerow([report_type_value, today_str()])
        return buf.getvalue()

    async def build_report_csv_for_organization(
        self, db: AsyncSession, target_org: str, report_type: Any
    ) -> str:
        """Build report CSV content for a tenant without a request user.

        Reserved for the scheduled-report background job; not exposed via API.
        """
        report_type_value = _normalize_report_type(report_type)
        if report_type_value not in VALID_REPORT_TYPES:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid report type '{report_type_value}'. Valid types: {sorted(VALID_REPORT_TYPES)}",
            )
        payload = await self._build_report_payload(
            db, report_type_value, None, target_org=target_org
        )
        return self._rows_to_csv(
            report_type_value, payload.get("metrics", {}).get("table_rows") or []
        )

    async def export_report_csv(
        self,
        db: AsyncSession,
        report_type: Any = ReportTypeEnum.SALES_PERFORMANCE,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        report_type_value = _normalize_report_type(report_type)
        if report_type_value not in VALID_REPORT_TYPES:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid report type '{report_type_value}'. Valid types: {sorted(VALID_REPORT_TYPES)}",
            )

        target_org = await self._resolve_org_id(db, org_id, current_user)
        requesting_user_id = (
            current_user.id if current_user and getattr(current_user, "id", None) else None
        )
        if not requesting_user_id:
            raise ForbiddenError(
                message="Authenticated user is required to export reports.",
            )

        # Export the requested report's actual computed rows.
        payload = await self._build_report_payload(db, report_type_value, current_user)
        csv_content = self._rows_to_csv(
            report_type_value, payload.get("metrics", {}).get("table_rows") or []
        ).encode("utf-8")
        object_name = _build_export_object_key(target_org, "csv")
        try:
            file_obj = io.BytesIO(csv_content)
            s3_key = await asyncio.to_thread(
                s3_service.upload_file,
                file_obj,
                object_name=object_name,
                content_type="text/csv",
            )
            csv_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
        except Exception as e:
            logger.exception(
                "S3 upload failed for CSV export org=%s report=%s", target_org, report_type_value
            )
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to upload CSV to storage. Please try again later.",
            ) from e

        try:
            export = await self.repository.create_export(
                db,
                data={
                    "organization_id": target_org,
                    "report_type": report_type_value,
                    "file_format": "csv",
                    "download_url": None,
                    "s3_key": s3_key,
                    "requested_by": requesting_user_id,
                },
            )
            await self._commit(db, "Failed to record CSV export")
            await db.refresh(export)
            return {"csv_url": csv_url, "export_id": export.id}
        except Exception as e:
            await db.rollback()
            await _cleanup_export_object(s3_key)
            if isinstance(e, APIException):
                raise
            logger.exception(
                "Failed to record CSV export for org=%s report=%s", target_org, report_type_value
            )
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to complete CSV export. Please try again later.",
            ) from e

    async def schedule_report_email(
        self,
        db: AsyncSession,
        report_type: Any,
        email: str,
        frequency: str = "Weekly",
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        clean_email = (email or "").strip()
        if not clean_email or not EMAIL_REGEX.match(clean_email):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid email address '{email}'. Please provide a valid email format.",
            )

        clean_freq = (frequency or "Weekly").capitalize()
        if clean_freq not in VALID_FREQUENCIES:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid frequency '{frequency}'. Must be one of: {sorted(VALID_FREQUENCIES)}",
            )

        report_type_value = _normalize_report_type(report_type)
        if report_type_value not in VALID_REPORT_TYPES:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message=f"Invalid report type '{report_type_value}'. Valid types: {sorted(VALID_REPORT_TYPES)}",
            )

        target_org = await self._resolve_org_id(db, org_id, current_user)
        next_run_dt = compute_next_run(clean_freq)

        await self.repository.create_scheduled_report(
            db,
            data={
                "organization_id": target_org,
                "report_type": report_type_value,
                "email": clean_email,
                "frequency": clean_freq,
                "next_run": next_run_dt,
            },
        )
        await self._commit(db, "Failed to schedule report")
        return {
            "message": f"Scheduled {clean_freq} report delivery of '{report_type_value}' to {clean_email}",
            "status": "success",
        }

    async def list_scheduled_reports(
        self,
        db: AsyncSession,
        org_id: str | None = None,
        current_user: User | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        target_org = await self._resolve_org_id(db, org_id, current_user)
        items = await self.repository.list_scheduled_reports(
            db, target_org, limit=limit, offset=offset
        )
        now = datetime.now(UTC)
        return [
            {
                "id": s.id,
                "report_type": s.report_type,
                "email": s.email,
                "frequency": s.frequency,
                "next_run": s.next_run.strftime("%Y-%m-%d") if s.next_run else today_str(),  # type: ignore[attr-defined]
                "status": (
                    "Processing"
                    if s.claimed_until is not None and s.claimed_until > now
                    else "Scheduled"
                ),
            }
            for s in items
        ]

    async def delete_scheduled_report(
        self,
        db: AsyncSession,
        schedule_id: str,
        org_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        target_org = await self._resolve_org_id(db, org_id, current_user)
        report = await self.repository.get_scheduled_report(db, schedule_id, target_org)
        if not report:
            raise NotFoundError(message=f"Scheduled report with id '{schedule_id}' not found.")

        await self.repository.delete_scheduled_report(db, report)
        await self._commit(db, "Failed to delete scheduled report")
        return {
            "message": f"Scheduled report {schedule_id} deleted successfully",
            "status": "success",
        }

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=error_message
            ) from e


report_service = ReportService()
