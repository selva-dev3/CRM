import json

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

    async def get_kpis(self, db: AsyncSession) -> dict:
        total_leads = await self.repository.count_leads(db)
        deals_won_amount = await self.repository.sum_won_deals(db)
        total_deals = await self.repository.count_deals(db)
        won_deals = await self.repository.count_won_deals(db)
        win_rate = round((won_deals / total_deals * 100.0), 2) if total_deals > 0 else 0.0
        avg_score = await self.repository.avg_lead_score(db)

        recent_activity = []
        for lead in await self.repository.recent_leads(db):
            recent_activity.append(
                {
                    "action": "New Lead Added",
                    "title": f"{getattr(lead, 'first_name', '') or ''} {getattr(lead, 'last_name', '') or ''}".strip()
                    or getattr(lead, "name", "")
                    or lead.email,
                    "user": "System API",
                    "timestamp": str(lead.created_at)[:16] if getattr(lead, "created_at", None) else "Recent",
                }
            )

        return {
            "total_leads": total_leads,
            "deals_won_amount": deals_won_amount,
            "win_rate_percentage": win_rate,
            "ai_lead_score_avg": avg_score,
            "recent_activity": recent_activity,
        }

    async def get_sales_funnel(self, db: AsyncSession) -> list[dict]:
        rows = await self.repository.deal_stage_totals(db)
        stage_map = {stage: {"count": count, "value": value} for stage, count, value in rows if stage}

        all_stages = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
        result = []
        for stg in all_stages:
            info = stage_map.get(stg, {"count": 0, "value": 0.0})
            result.append({"stage": stg, "count": info["count"], "value": info["value"]})

        for stg, info in stage_map.items():
            if stg not in all_stages:
                result.append({"stage": stg, "count": info["count"], "value": info["value"]})

        return result

    async def get_revenue_chart(self, db: AsyncSession) -> dict:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]
        won_total = await self.repository.sum_won_deals(db)
        actual = (
            [round(won_total * factor, 2) for factor in [0.1, 0.12, 0.15, 0.18, 0.2, 0.22, 0.25]]
            if won_total > 0
            else [0, 0, 0, 0, 0, 0, 0]
        )
        target = [40000, 50000, 55000, 60000, 65000, 75000, 85000]
        return {"months": months, "actual": actual, "target": target}

    async def get_top_performers(self, db: AsyncSession) -> list[dict]:
        rows = await self.repository.top_performers(db)
        result = []
        for owner_name, deals_count, revenue in rows:
            owner_name = owner_name or "Unassigned Rep"
            avatar = owner_name[:2].upper() if owner_name else "UR"
            result.append(
                {"name": owner_name, "deals_count": deals_count, "revenue": float(revenue), "avatar": avatar}
            )
        return result

    async def get_lead_conversions(self, db: AsyncSession) -> list[dict]:
        rows = await self.repository.lead_source_counts(db)
        result = []
        for source, lead_count in rows:
            source_name = source if source else "Organic / Direct"
            converted = await self.repository.count_converted_leads_by_source(db, source)
            rate = round((converted / lead_count * 100.0), 1) if lead_count > 0 else 0.0
            result.append({"source": source_name, "leads": lead_count, "converted": converted, "rate": rate})
        return result

    async def get_activities_summary(self, db: AsyncSession) -> dict:
        return {
            "calls_completed": await self.repository.count_calls(db),
            "emails_sent": await self.repository.count_emails(db),
            "meetings_held": await self.repository.count_meetings(db),
            "tasks_completed": await self.repository.count_completed_tasks(db),
        }

    async def get_recent_deals(self, db: AsyncSession) -> list[dict]:
        deals = await self.repository.recent_deals(db)
        return [
            {
                "deal_id": d.id,
                "title": d.title,
                "amount": float(d.amount or 0.0),
                "stage": d.stage or "Prospecting",
                "owner": d.assigned_to or "Unassigned",
                "updated_at": str(d.created_at)[:10] if getattr(d, "created_at", None) else "Today",
            }
            for d in deals
        ]

    async def get_ai_insights(self, db: AsyncSession) -> dict:
        total_leads = await self.repository.count_leads(db)
        total_deals, total_amount = await self.repository.count_deals_and_sum(db)
        summary_text = (
            f"AI Pipeline Analysis: Database tracks {total_leads} active lead(s) and {total_deals} deal(s) "
            f"with total pipeline value of ${total_amount:,.2f}."
        )

        insights_list = []
        recent_deal = await self.repository.top_deal(db)
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

    async def get_custom_widgets(self, db: AsyncSession) -> list[dict]:
        try:
            setting = await self.setting_repository.get_by_key(db, "dashboard_custom_widgets")
            if setting and setting.value:
                return json.loads(setting.value)
        except Exception:
            pass
        return [
            {"id": "w-kpis", "title": "Executive KPIs", "enabled": True},
            {"id": "w-funnel", "title": "Sales Stage Funnel", "enabled": True},
            {"id": "w-revenue", "title": "Monthly Revenue Chart", "enabled": True},
            {"id": "w-top", "title": "Top Sales Performers", "enabled": True},
            {"id": "w-deals", "title": "Priority Deals", "enabled": True},
            {"id": "w-ai", "title": "AI Recommendations", "enabled": True},
        ]

    async def save_custom_widgets(self, db: AsyncSession, widgets: list[dict]) -> dict:
        try:
            await self.setting_repository.upsert(
                db, key="dashboard_custom_widgets", value=json.dumps(widgets)
            )
            await db.commit()
            return {"message": "Dashboard widget layout preferences saved to Database", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e


dashboard_service = DashboardService()
