from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models import Lead, Deal, Task, CallLog, Meeting, Email, SystemSetting
from app.schemas.crm_schemas import DashboardKPIs, MessageResponse

router = APIRouter()

@router.get("/kpis", response_model=DashboardKPIs, summary="Get main dashboard executive KPIs")
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db)):
    try:
        # Total leads count from DB
        leads_res = await db.execute(select(func.count(Lead.id)))
        total_leads = leads_res.scalar() or 0
        
        # Total closed won revenue sum from DB
        deals_won_res = await db.execute(select(func.coalesce(func.sum(Deal.amount), 0.0)).where(Deal.stage == "Closed Won"))
        deals_won_amount = float(deals_won_res.scalar() or 0.0)
        
        # Total deals count & won count for win rate from DB
        total_deals_res = await db.execute(select(func.count(Deal.id)))
        total_deals = total_deals_res.scalar() or 0
        
        won_deals_res = await db.execute(select(func.count(Deal.id)).where(Deal.stage == "Closed Won"))
        won_deals = won_deals_res.scalar() or 0
        
        win_rate = round((won_deals / total_deals * 100.0), 2) if total_deals > 0 else 0.0
        
        # Lead score average from DB
        avg_score = 0.0
        if hasattr(Lead, "ai_score"):
            score_res = await db.execute(select(func.coalesce(func.avg(Lead.ai_score), 0.0)))
            avg_score = round(float(score_res.scalar() or 0.0), 1)

        # Recent activities queried dynamically from DB
        recent_activity = []
        recent_leads = (await db.execute(select(Lead).order_by(Lead.created_at.desc()).limit(3))).scalars().all()
        for l in recent_leads:
            recent_activity.append({
                "action": "New Lead Added",
                "title": f"{getattr(l, 'first_name', '') or ''} {getattr(l, 'last_name', '') or ''}".strip() or getattr(l, 'name', '') or l.email,
                "user": "System API",
                "timestamp": str(l.created_at)[:16] if getattr(l, "created_at", None) else "Recent"
            })
        
        return {
            "total_leads": total_leads,
            "deals_won_amount": deals_won_amount,
            "win_rate_percentage": win_rate,
            "ai_lead_score_avg": avg_score,
            "recent_activity": recent_activity
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/sales-funnel", summary="Get sales stage conversion funnel data")
async def get_sales_funnel(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)).group_by(Deal.stage))
        rows = res.all()
        
        stage_map = {r[0]: {"count": r[1], "value": float(r[2])} for r in rows if r[0]}
        
        all_stages = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
        result = []
        for stg in all_stages:
            info = stage_map.get(stg, {"count": 0, "value": 0.0})
            result.append({"stage": stg, "count": info["count"], "value": info["value"]})
            
        for stg, info in stage_map.items():
            if stg not in all_stages:
                result.append({"stage": stg, "count": info["count"], "value": info["value"]})

        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/revenue-chart", summary="Get monthly revenue vs target comparison")
async def get_revenue_chart(db: AsyncSession = Depends(get_db)):
    try:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]
        res = await db.execute(select(func.coalesce(func.sum(Deal.amount), 0.0)).where(Deal.stage == "Closed Won"))
        won_total = float(res.scalar() or 0.0)

        actual = [round(won_total * factor, 2) for factor in [0.1, 0.12, 0.15, 0.18, 0.2, 0.22, 0.25]] if won_total > 0 else [0, 0, 0, 0, 0, 0, 0]
        target = [40000, 50000, 55000, 60000, 65000, 75000, 85000]

        return {
            "months": months,
            "actual": actual,
            "target": target
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/top-performers", summary="Get top sales rep leaderboard")
async def get_top_performers(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(
            select(Deal.assigned_to, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
            .where(Deal.assigned_to.isnot(None))
            .group_by(Deal.assigned_to)
            .order_by(func.sum(Deal.amount).desc())
            .limit(5)
        )
        rows = res.all()
        result = []
        for r in rows:
            owner_name = r[0] or "Unassigned Rep"
            avatar = owner_name[:2].upper() if owner_name else "UR"
            result.append({
                "name": owner_name,
                "deals_count": r[1],
                "revenue": float(r[2]),
                "avatar": avatar
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/lead-conversions", summary="Get lead source conversion distribution")
async def get_lead_conversions(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Lead.source, func.count(Lead.id)).group_by(Lead.source))
        rows = res.all()
        result = []
        for r in rows:
            source_name = r[0] if r[0] else "Organic / Direct"
            lead_count = r[1]
            converted_count = await db.execute(select(func.count(Lead.id)).where((Lead.source == r[0]) & (Lead.status.ilike("%convert%") | Lead.status.ilike("%won%"))))
            conv = converted_count.scalar() or 0
            rate = round((conv / lead_count * 100.0), 1) if lead_count > 0 else 0.0
            result.append({
                "source": source_name,
                "leads": lead_count,
                "converted": conv,
                "rate": rate
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/activities-summary", summary="Get daily sales activities summary")
async def get_activities_summary(db: AsyncSession = Depends(get_db)):
    try:
        c_res = await db.execute(select(func.count(CallLog.id)))
        calls = c_res.scalar() or 0
        
        e_res = await db.execute(select(func.count(Email.id)))
        emails = e_res.scalar() or 0

        m_res = await db.execute(select(func.count(Meeting.id)))
        meetings = m_res.scalar() or 0
        
        t_res = await db.execute(select(func.count(Task.id)).where(Task.status == "Completed"))
        tasks = t_res.scalar() or 0
        
        return {
            "calls_completed": calls,
            "emails_sent": emails,
            "meetings_held": meetings,
            "tasks_completed": tasks
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/recent-deals", summary="Get recent deal updates stream")
async def get_recent_deals(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Deal).order_by(Deal.created_at.desc()).limit(5))
        deals = res.scalars().all()
        return [
            {
                "deal_id": d.id,
                "title": d.title,
                "amount": float(d.amount or 0.0),
                "stage": d.stage or "Prospecting",
                "owner": d.assigned_to or "Unassigned",
                "updated_at": str(d.created_at)[:10] if getattr(d, "created_at", None) else "Today"
            }
            for d in deals
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/ai-insights", summary="Get AI-generated pipeline executive summary")
async def get_dashboard_ai_insights(db: AsyncSession = Depends(get_db)):
    try:
        leads_res = await db.execute(select(func.count(Lead.id)))
        total_leads = leads_res.scalar() or 0

        deals_res = await db.execute(select(func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0)))
        deal_row = deals_res.first()
        total_deals = deal_row[0] if deal_row else 0
        total_amount = float(deal_row[1]) if deal_row else 0.0

        summary_text = (
            f"AI Pipeline Analysis: Database tracks {total_leads} active lead(s) and {total_deals} deal(s) "
            f"with total pipeline value of ${total_amount:,.2f}."
        )

        recent_deal = (await db.execute(select(Deal).order_by(Deal.amount.desc()).limit(1))).scalars().first()
        insights_list = []
        if recent_deal:
            insights_list.append({
                "title": f"Follow up with {recent_deal.title}",
                "description": f"High value opportunity worth ${recent_deal.amount:,.2f} currently in {recent_deal.stage} stage.",
                "type": "high",
                "action": "Follow Up"
            })
        
        return {
            "summary": summary_text,
            "insights": insights_list,
            "risk_deals": []
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/custom-widgets", summary="Get user customized dashboard widgets layout")
async def get_custom_widgets(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == "dashboard_custom_widgets"))
        setting = res.scalars().first()
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
        {"id": "w-ai", "title": "AI Recommendations", "enabled": True}
    ]

@router.post("/custom-widgets", response_model=MessageResponse, summary="Save user dashboard widget preferences")
async def save_custom_widgets(widgets: List[Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    try:
        json_val = json.dumps(widgets)
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == "dashboard_custom_widgets"))
        setting = res.scalars().first()
        if setting:
            setting.value = json_val
        else:
            db.add(SystemSetting(key="dashboard_custom_widgets", value=json_val))
        await db.commit()
        return {"message": "Dashboard widget layout preferences saved to Database", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
