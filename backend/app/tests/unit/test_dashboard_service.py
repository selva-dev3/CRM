from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.setting_repository import SettingRepository
from app.services.dashboard_service import DashboardService


def _service_with(repo: DashboardRepository, setting_repo: SettingRepository) -> DashboardService:
    return DashboardService(repository=repo, setting_repository=setting_repo)


@pytest.mark.asyncio
async def test_get_kpis_computes_win_rate():
    repo = DashboardRepository()
    repo.count_leads = AsyncMock(return_value=10)
    repo.sum_pipeline_deals = AsyncMock(return_value=12000.0)
    repo.sum_won_deals = AsyncMock(return_value=5000.0)
    repo.count_closed_deals = AsyncMock(return_value=8)
    repo.count_won_deals = AsyncMock(return_value=2)
    repo.avg_lead_score = AsyncMock(return_value=0.0)
    repo.count_scored_leads = AsyncMock(return_value=10)
    repo.recent_leads = AsyncMock(return_value=[])
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_kpis(db, "org-1")

    assert result["total_leads"] == 10
    assert result["deals_won_amount"] == 5000.0
    assert result["pipeline_revenue"] == 12000.0
    assert result["win_rate_percentage"] == 25.0
    assert result["won_deals_count"] == 2
    assert result["closed_deals_count"] == 8
    assert result["ai_lead_score_avg"] == 0.0
    assert result["scored_leads_count"] == 10
    repo.count_leads.assert_awaited_once_with(db, "org-1")


@pytest.mark.asyncio
async def test_get_sales_funnel_orders_standard_stages_first():
    repo = DashboardRepository()
    repo.deal_stage_totals = AsyncMock(
        return_value=[("Closed Won", 3, 1000.0), ("Custom Stage", 1, 50.0)]
    )
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_sales_funnel(db, "org-1")

    stages = [item["stage"] for item in result]
    assert stages.index("Prospecting") == 0
    assert stages.index("Closed Won") == 4
    assert stages[-1] == "Custom Stage"


@pytest.mark.asyncio
async def test_get_custom_widgets_returns_defaults_when_unset():
    setting_repo = SettingRepository()
    setting_repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_custom_widgets(db, "org-1")

    assert len(result) == 6
    assert result[0]["id"] == "w-kpis"
    setting_repo.get_by_key.assert_awaited_once_with(db, "dashboard_custom_widgets:org-1")


@pytest.mark.asyncio
async def test_save_custom_widgets_persists_preferences():
    setting_repo = SettingRepository()
    setting_repo.upsert = AsyncMock()
    service = _service_with(DashboardRepository(), setting_repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.save_custom_widgets(db, "org-1", [{"id": "w-kpis", "enabled": True}])

    assert result["status"] == "success"
    setting_repo.upsert.assert_awaited_once_with(
        db,
        key="dashboard_custom_widgets:org-1",
        value='[{"id": "w-kpis", "enabled": true}]',
    )


@pytest.mark.asyncio
async def test_get_activities_summary_counts_each_metric():
    repo = DashboardRepository()
    repo.get_organization_timezone = AsyncMock(return_value="UTC")
    repo.count_calls = AsyncMock(return_value=5)
    repo.count_emails = AsyncMock(return_value=8)
    repo.count_meetings = AsyncMock(return_value=2)
    repo.count_completed_tasks = AsyncMock(return_value=11)
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_activities_summary(db, "org-1")

    assert result["calls_completed"] == 5
    assert result["emails_sent"] == 8
    assert result["meetings_held"] == 2
    assert result["tasks_completed"] == 11
    assert result["period_label"] == "Today · UTC"
    assert repo.count_calls.await_args.args[1] == "org-1"


@pytest.mark.asyncio
async def test_get_lead_conversions_merges_equivalent_urls():
    repo = DashboardRepository()
    repo.lead_source_counts = AsyncMock(
        return_value=[("https://Selv.in/", 2), ("https://selv.in", 3)]
    )
    repo.count_converted_leads_by_source = AsyncMock(side_effect=[1, 2])
    service = _service_with(repo, SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_lead_conversions(db, "org-1")

    assert result == [{"source": "selv.in", "leads": 5, "converted": 3, "rate": 60.0}]
