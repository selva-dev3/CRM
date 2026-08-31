import json
from datetime import UTC, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.setting_repository import SettingRepository


class DashboardService:
    """Business logic for dashboard aggregate data and widgets."""

    def __init__(
        self,
        repository: DashboardRepository | None = None,
        setting_repository: SettingRepository | None = None,
    ) -> None:
        self.repository = repository or DashboardRepository()
        self.setting_repository = setting_repository or SettingRepository()

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

    async def get_kpis(self, db: AsyncSession, organization_id: str) -> dict:
        total_leads = await self.repository.count_leads(db, organization_id)
        pipeline_revenue = await self.repository.sum_pipeline_deals(db, organization_id)
        deals_won_amount = await self.repository.sum_won_deals(db, organization_id)
        closed_deals = await self.repository.count_closed_deals(db, organization_id)
        won_deals = await self.repository.count_won_deals(db, organization_id)
        win_rate = round((won_deals / closed_deals * 100.0), 2) if closed_deals > 0 else 0.0
        avg_score = await self.repository.avg_lead_score(db, organization_id)
        scored_leads = await self.repository.count_scored_leads(db, organization_id)

        recent_activity = []
        for lead in await self.repository.recent_leads(db, organization_id):
            recent_activity.append(
                {
                    "action": "New Lead Added",
                    "title": lead.contact_name or lead.title or lead.email,
                    "user": "System API",
                    "timestamp": str(lead.created_at)[:16]
                    if getattr(lead, "created_at", None)
                    else "Recent",
                }
            )

        return {
            "total_leads": total_leads,
            "deals_won_amount": deals_won_amount,
            "pipeline_revenue": pipeline_revenue,
            "win_rate_percentage": win_rate,
            "won_deals_count": won_deals,
            "closed_deals_count": closed_deals,
            "ai_lead_score_avg": avg_score,
            "scored_leads_count": scored_leads,
            "recent_activity": recent_activity,
        }

    async def get_sales_funnel(self, db: AsyncSession, organization_id: str) -> list[dict]:
        rows = await self.repository.deal_stage_totals(db, organization_id)
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

    async def get_revenue_chart(self, db: AsyncSession, organization_id: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="METRIC_UNAVAILABLE",
            message=(
                "Monthly revenue is unavailable until closed-deal timestamps and "
                "organization revenue targets are recorded."
            ),
        )

    async def get_top_performers(self, db: AsyncSession, organization_id: str) -> list[dict]:
        rows = await self.repository.top_performers(db, organization_id)
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

    async def get_lead_conversions(self, db: AsyncSession, organization_id: str) -> list[dict]:
        rows = await self.repository.lead_source_conversions(db, organization_id)
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
                "rate": round((counts["converted"] / counts["leads"] * 100.0), 1)
                if counts["leads"] > 0
                else 0.0,
            }
            for source, counts in grouped.items()
        ]

    async def get_activities_summary(self, db: AsyncSession, organization_id: str) -> dict:
        timezone_name = await self.repository.get_organization_timezone(db, organization_id)
        try:
            organization_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone_name = "UTC"
            organization_timezone = ZoneInfo("UTC")

        now_utc = datetime.now(UTC)
        local_now = now_utc.astimezone(organization_timezone)
        local_start = datetime.combine(local_now.date(), time.min, tzinfo=organization_timezone)
        local_end = local_start + timedelta(days=1)
        start_utc = local_start.astimezone(UTC)
        end_utc = local_end.astimezone(UTC)

        return {
            "calls_completed": await self.repository.count_calls(
                db, organization_id, start_utc, end_utc
            ),
            "emails_sent": await self.repository.count_emails(
                db, organization_id, start_utc, end_utc
            ),
            "meetings_held": await self.repository.count_meetings(
                db, organization_id, start_utc, min(end_utc, now_utc)
            ),
            "tasks_completed": await self.repository.count_completed_tasks(
                db, organization_id, start_utc, end_utc
            ),
            "period_label": f"Today · {timezone_name}",
        }

    async def get_recent_deals(self, db: AsyncSession, organization_id: str) -> list[dict]:
        deals = await self.repository.recent_deals(db, organization_id)
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

    async def get_ai_insights(self, db: AsyncSession, organization_id: str) -> dict:
        total_leads = await self.repository.count_leads(db, organization_id)
        total_deals, total_amount = await self.repository.count_deals_and_sum(db, organization_id)
        summary_text = (
            f"AI Pipeline Analysis: Database tracks {total_leads} active lead(s) and {total_deals} deal(s) "
            f"with total pipeline value of ${total_amount:,.2f}."
        )

        insights_list = []
        recent_deal = await self.repository.top_deal(db, organization_id)
        if recent_deal:
            insights_list.append(
                {
                    "title": f"Follow up with {recent_deal.title}",
                    "description": f"High value opportunity worth ${recent_deal.amount:,.2f} currently in {recent_deal.stage} stage.",
                    "type": "high",
                    "action": "Follow Up",
                }
            )

        return {"summary": summary_text, "insights": insights_list, "risk_deals": []}

    async def get_custom_widgets(self, db: AsyncSession, organization_id: str) -> list[dict]:
        setting = await self.setting_repository.get_by_key(
            db, f"dashboard_custom_widgets:{organization_id}"
        )
        if setting and setting.value:
            return json.loads(setting.value)
        return [
            {"id": "w-kpis", "title": "Executive KPIs", "enabled": True},
            {"id": "w-funnel", "title": "Sales Stage Funnel", "enabled": True},
            {"id": "w-top", "title": "Top Sales Performers", "enabled": True},
            {"id": "w-deals", "title": "Priority Deals", "enabled": True},
            {"id": "w-ai", "title": "AI Recommendations", "enabled": True},
        ]

    async def save_custom_widgets(
        self, db: AsyncSession, organization_id: str, widgets: list[dict]
    ) -> dict:
        try:
            await self.setting_repository.upsert(
                db,
                key=f"dashboard_custom_widgets:{organization_id}",
                value=json.dumps(widgets),
            )
            await db.commit()
            return {
                "message": "Dashboard widget layout preferences saved to Database",
                "status": "success",
            }
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e


dashboard_service = DashboardService()
