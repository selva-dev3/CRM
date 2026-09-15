import json
from datetime import UTC, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import User
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.dashboard import DashboardKPIs
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.record_access_service import record_access_service


class DashboardService:
    """Business logic for dashboard aggregate data and widgets."""

    DEFAULT_WIDGETS = [
        {"id": "w-kpis", "title": "Executive KPIs", "enabled": True},
        {"id": "w-revenue", "title": "Won Revenue Trend", "enabled": True},
        {"id": "w-funnel", "title": "Sales Pipeline", "enabled": True},
        {"id": "w-conversions", "title": "Lead Channels", "enabled": True},
        {"id": "w-activity", "title": "Activity Summary", "enabled": True},
        {"id": "w-contacts", "title": "Recent Contacts", "enabled": True},
        {"id": "w-deals", "title": "Recent Deals", "enabled": True},
        {"id": "w-top", "title": "Top Performers", "enabled": True},
        {"id": "w-ai", "title": "AI Recommendations", "enabled": True},
    ]

    def __init__(
        self,
        repository: DashboardRepository | None = None,
        setting_repository: SettingRepository | None = None,
        ai_service_instance: AIDomainService | None = None,
    ) -> None:
        self.repository = repository or DashboardRepository()
        self.setting_repository = setting_repository or SettingRepository()
        self.ai_service = ai_service_instance or ai_domain_service

    @staticmethod
    def _normalize_lead_source(source: str | None) -> str:
        raw_source = (source or "").strip()
        if not raw_source:
            return "Organic / Direct"

        if raw_source.lower().startswith(("http://", "https://")):
            parsed = urlsplit(raw_source)
            hostname = (parsed.hostname or "").lower().removeprefix("www.")
            path = parsed.path.rstrip("/")
            return f"{hostname}{path}" if hostname else raw_source

        return raw_source

    @staticmethod
    def _comparison(current: float, previous: float) -> dict:
        return {
            "previous_value": previous,
            "change_percentage": (
                round((current - previous) / previous * 100.0, 1) if previous > 0 else None
            ),
        }

    async def get_kpis(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        current_user: User | None = None,
    ) -> DashboardKPIs:
        lead_access = (
            await record_access_service.resolve(db, current_user, "leads") if current_user else None
        )
        deal_access = (
            await record_access_service.resolve(db, current_user, "deals") if current_user else None
        )
        quote_access = (
            await record_access_service.resolve(db, current_user, "quotes")
            if current_user
            else None
        )
        invoice_access = (
            await record_access_service.resolve(db, current_user, "invoices")
            if current_user
            else None
        )
        payment_access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        lead_metrics = await self.repository.lead_kpi_metrics(
            db, organization_id, lead_access, start_at=start_at, end_at=end_at
        )
        deal_metrics = await self.repository.deal_kpi_metrics(
            db, organization_id, deal_access, start_at=start_at, end_at=end_at
        )
        total_leads = int(lead_metrics["total_leads"])
        avg_score = float(lead_metrics["average_score"])
        scored_leads = int(lead_metrics["scored_leads"])
        pipeline_revenue = float(deal_metrics["pipeline_revenue"])
        deals_won_amount = float(deal_metrics["deals_won_amount"])
        closed_deals = int(deal_metrics["closed_deals"])
        won_deals = int(deal_metrics["won_deals"])
        win_rate = round((won_deals / closed_deals * 100.0), 2) if closed_deals > 0 else 0.0
        currency, locale = await self.repository.get_organization_currency_locale(
            db, organization_id
        )
        financial = await self.repository.financial_kpis(
            db,
            organization_id,
            currency=currency,
            start_at=start_at,
            end_at=end_at,
            quote_access=quote_access,
            invoice_access=invoice_access,
            payment_access=payment_access,
        )

        comparisons = None
        if start_at is not None and end_at is not None:
            duration = end_at - start_at
            previous_start, previous_end = start_at - duration, start_at
            previous_lead_metrics = await self.repository.lead_kpi_metrics(
                db, organization_id, lead_access, start_at=previous_start, end_at=previous_end
            )
            previous_deal_metrics = await self.repository.deal_kpi_metrics(
                db, organization_id, deal_access, start_at=previous_start, end_at=previous_end
            )
            previous_leads = int(previous_lead_metrics["total_leads"])
            previous_won_amount = float(previous_deal_metrics["deals_won_amount"])
            previous_closed = int(previous_deal_metrics["closed_deals"])
            previous_won = int(previous_deal_metrics["won_deals"])
            previous_win_rate = (
                round(previous_won / previous_closed * 100.0, 2) if previous_closed else 0.0
            )
            previous_financial = await self.repository.financial_kpis(
                db,
                organization_id,
                currency=currency,
                start_at=previous_start,
                end_at=previous_end,
                quote_access=quote_access,
                invoice_access=invoice_access,
                payment_access=payment_access,
            )
            comparisons = {
                "total_leads": self._comparison(total_leads, previous_leads),
                "deals_won_amount": self._comparison(deals_won_amount, previous_won_amount),
                "won_deals_count": self._comparison(won_deals, previous_won),
                "win_rate_percentage": self._comparison(win_rate, previous_win_rate),
                "quote_value": self._comparison(
                    financial["quote_value"], previous_financial["quote_value"]
                ),
                "revenue": self._comparison(financial["revenue"], previous_financial["revenue"]),
            }

        return DashboardKPIs(
            total_leads=total_leads,
            deals_won_amount=deals_won_amount,
            pipeline_revenue=pipeline_revenue,
            win_rate_percentage=win_rate,
            won_deals_count=won_deals,
            closed_deals_count=closed_deals,
            ai_lead_score_avg=avg_score,
            scored_leads_count=scored_leads,
            **financial,
            currency=currency,
            locale=locale,
            recent_activity=[],
            period={"start_at": start_at, "end_at": end_at} if start_at and end_at else None,
            comparisons=comparisons,
        )

    async def get_sales_funnel(
        self, db: AsyncSession, organization_id: str, current_user: User | None = None
    ) -> list[dict]:
        access = (
            await record_access_service.resolve(db, current_user, "deals") if current_user else None
        )
        rows = await self.repository.deal_stage_totals(db, organization_id, access)
        stage_map = {
            stage: {"count": count, "value": value} for stage, count, value in rows if stage
        }

        all_stages = [
            "Prospecting",
            "Qualification",
            "Proposal",
            "Negotiation",
            "Closed Won",
            "Closed Lost",
        ]
        result = []
        for stg in all_stages:
            info = stage_map.get(stg, {"count": 0, "value": 0.0})
            result.append({"stage": stg, "count": info["count"], "value": info["value"]})

        for stg, info in stage_map.items():
            if stg not in all_stages:
                result.append({"stage": stg, "count": info["count"], "value": info["value"]})

        return result

    async def get_revenue_chart(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        start_at: datetime,
        end_at: datetime,
        current_user: User | None = None,
    ) -> dict:
        access = (
            await record_access_service.resolve(db, current_user, "deals") if current_user else None
        )
        rows = await self.repository.monthly_won_revenue(
            db, organization_id, start_at, end_at, access
        )
        revenue_by_month = {(month.year, month.month): float(value or 0.0) for month, value in rows}
        cursor = datetime(start_at.year, start_at.month, 1, tzinfo=start_at.tzinfo)
        months: list[str] = []
        actual: list[float] = []
        while cursor < end_at:
            months.append(cursor.strftime("%b %Y"))
            actual.append(revenue_by_month.get((cursor.year, cursor.month), 0.0))
            cursor = (
                cursor.replace(year=cursor.year + 1, month=1)
                if cursor.month == 12
                else cursor.replace(month=cursor.month + 1)
            )
        return {"months": months, "actual": actual, "target": []}

    async def get_top_performers(
        self,
        db: AsyncSession,
        organization_id: str,
        current_user: User | None = None,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict]:
        access = (
            await record_access_service.resolve(db, current_user, "deals") if current_user else None
        )
        rows = await self.repository.top_performers(
            db, organization_id, access=access, start_at=start_at, end_at=end_at
        )
        result = []
        for owner_name, deals_count, revenue in rows:
            owner_name = owner_name or "Unassigned Rep"
            avatar = owner_name[:2].upper() if owner_name else "UR"
            result.append(
                {
                    "name": owner_name,
                    "deals_count": deals_count,
                    "revenue": float(revenue),
                    "avatar": avatar,
                }
            )
        return result

    async def get_lead_conversions(
        self,
        db: AsyncSession,
        organization_id: str,
        current_user: User | None = None,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict]:
        access = (
            await record_access_service.resolve(db, current_user, "leads") if current_user else None
        )
        rows = await self.repository.lead_source_conversions(
            db, organization_id, access, start_at=start_at, end_at=end_at
        )
        grouped: dict[str, dict[str, int]] = {}
        for source, lead_count, converted_count in rows:
            source_name = self._normalize_lead_source(source)
            item = grouped.setdefault(source_name, {"leads": 0, "converted": 0})
            item["leads"] += lead_count
            item["converted"] += converted_count

        return [
            {
                "source": source,
                "leads": counts["leads"],
                "converted": counts["converted"],
                "rate": (
                    round((counts["converted"] / counts["leads"] * 100.0), 1)
                    if counts["leads"] > 0
                    else 0.0
                ),
            }
            for source, counts in grouped.items()
        ]

    async def get_activities_summary(
        self,
        db: AsyncSession,
        organization_id: str,
        current_user: User | None = None,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        timezone_name = await self.repository.get_organization_timezone(db, organization_id)
        try:
            organization_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone_name = "UTC"
            organization_timezone = ZoneInfo("UTC")

        now_utc = datetime.now(UTC)
        if start_at is not None and end_at is not None:
            start_utc, end_utc = start_at, end_at
            period_label = f"Selected period · {timezone_name}"
        else:
            local_now = now_utc.astimezone(organization_timezone)
            local_start = datetime.combine(local_now.date(), time.min, tzinfo=organization_timezone)
            local_end = local_start + timedelta(days=1)
            start_utc, end_utc = local_start.astimezone(UTC), local_end.astimezone(UTC)
            period_label = f"Today · {timezone_name}"
        access = (
            {
                module: await record_access_service.resolve(db, current_user, module)
                for module in ("calls", "emails", "meetings", "tasks")
            }
            if current_user
            else {}
        )

        return {
            "calls_completed": await self.repository.count_calls(
                db, organization_id, start_utc, end_utc, access.get("calls")
            ),
            "emails_sent": await self.repository.count_emails(
                db, organization_id, start_utc, end_utc, access.get("emails")
            ),
            "meetings_held": await self.repository.count_meetings(
                db,
                organization_id,
                start_utc,
                min(end_utc, now_utc),
                access.get("meetings"),
            ),
            "tasks_completed": await self.repository.count_completed_tasks(
                db, organization_id, start_utc, end_utc, access.get("tasks")
            ),
            "period_label": period_label,
        }

    async def get_recent_deals(
        self,
        db: AsyncSession,
        organization_id: str,
        current_user: User | None = None,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[dict]:
        access = (
            await record_access_service.resolve(db, current_user, "deals") if current_user else None
        )
        deals = await self.repository.recent_deals(
            db, organization_id, limit=10, access=access, start_at=start_at, end_at=end_at
        )
        return [
            {
                "deal_id": d.id,
                "title": d.title,
                "amount": float(d.amount or 0.0),
                "stage": d.stage or "Prospecting",
                "owner": owner_name or "Unassigned",
                "updated_at": str(d.updated_at)[:10] if getattr(d, "updated_at", None) else "Today",
            }
            for d, owner_name in deals
        ]

    async def get_ai_insights(
        self, db: AsyncSession, organization_id: str, current_user: User
    ) -> dict:
        lead_access = await record_access_service.resolve(db, current_user, "leads")
        deal_access = await record_access_service.resolve(db, current_user, "deals")
        total_leads = await self.repository.count_leads(db, organization_id, lead_access)
        total_deals, total_amount = await self.repository.count_deals_and_sum(
            db, organization_id, deal_access
        )
        currency, _ = await self.repository.get_organization_currency_locale(db, organization_id)
        recent_deal = await self.repository.top_deal(db, organization_id, deal_access)
        context = {
            "metrics": {
                "total_leads": total_leads,
                "total_deals": total_deals,
                "total_pipeline_amount": total_amount,
                "currency": currency,
            },
            "deals": (
                [
                    {
                        "id": recent_deal.id,
                        "title": recent_deal.title,
                        "amount": recent_deal.amount,
                        "stage": recent_deal.stage,
                        "probability": recent_deal.probability,
                        "updated_at": recent_deal.updated_at,
                    }
                ]
                if recent_deal
                else []
            ),
        }
        return await self.ai_service.generate_dashboard_insights(db, context, current_user)

    async def get_custom_widgets(
        self, db: AsyncSession, organization_id: str, user_id: str | None = None
    ) -> list[dict]:
        setting = await self.setting_repository.get_by_key(
            db, f"dashboard_custom_widgets:{organization_id}:{user_id or 'shared'}"
        )
        if not setting and user_id:
            setting = await self.setting_repository.get_by_key(
                db, f"dashboard_custom_widgets:{organization_id}"
            )
        if setting and setting.value:
            try:
                saved = json.loads(setting.value)
                saved_by_id = {
                    item.get("id"): item
                    for item in saved
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                }
                merged = []
                for widget in self.DEFAULT_WIDGETS:
                    saved_enabled = saved_by_id.get(widget["id"], {}).get("enabled")
                    merged.append(
                        {
                            **widget,
                            "enabled": (
                                saved_enabled
                                if isinstance(saved_enabled, bool)
                                else widget["enabled"]
                            ),
                        }
                    )
                return merged
            except ValueError:
                # JSONDecodeError inherits from ValueError.
                return [widget.copy() for widget in self.DEFAULT_WIDGETS]
        return [widget.copy() for widget in self.DEFAULT_WIDGETS]

    async def save_custom_widgets(
        self,
        db: AsyncSession,
        organization_id: str,
        widgets: list[dict],
        user_id: str | None = None,
    ) -> dict:
        try:
            serialized_widgets = json.dumps(widgets)
        except (TypeError, ValueError) as exc:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_WIDGET_PREFERENCES",
                message="Dashboard widget preferences contain unsupported values.",
            ) from exc

        try:
            await self.setting_repository.upsert(
                db,
                key=f"dashboard_custom_widgets:{organization_id}:{user_id or 'shared'}",
                value=serialized_widgets,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {
            "message": "Dashboard widget layout preferences saved to Database",
            "status": "success",
        }


dashboard_service = DashboardService()
