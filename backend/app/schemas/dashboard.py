from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecentActivityResponse(BaseModel):
    action: str
    title: str
    user: str
    timestamp: str


class DashboardKPIs(BaseModel):
    total_leads: int = Field(ge=0)
    deals_won_amount: float = Field(ge=0)
    pipeline_revenue: float = Field(ge=0)
    win_rate_percentage: float = Field(ge=0, le=100)
    won_deals_count: int = Field(ge=0)
    closed_deals_count: int = Field(ge=0)
    ai_lead_score_avg: float = Field(ge=0, le=100)
    scored_leads_count: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    locale: str = Field(min_length=2, max_length=20)
    recent_activity: list[RecentActivityResponse]


class FunnelStageResponse(BaseModel):
    stage: str
    count: int = Field(ge=0)
    value: float = Field(ge=0)


class RevenueChartResponse(BaseModel):
    months: list[str]
    actual: list[float]
    target: list[float]


class UnavailableMetricResponse(BaseModel):
    code: Literal["METRIC_UNAVAILABLE"]
    message: str
    fields: None = None


class TopPerformerResponse(BaseModel):
    name: str
    deals_count: int = Field(ge=0)
    revenue: float = Field(ge=0)
    avatar: str


class LeadConversionResponse(BaseModel):
    source: str
    leads: int = Field(ge=0)
    converted: int = Field(ge=0)
    rate: float = Field(ge=0, le=100)


class ActivitiesSummaryResponse(BaseModel):
    calls_completed: int = Field(ge=0)
    emails_sent: int = Field(ge=0)
    meetings_held: int = Field(ge=0)
    tasks_completed: int = Field(ge=0)
    period_label: str


class RecentDealResponse(BaseModel):
    deal_id: str
    title: str
    amount: float = Field(ge=0)
    stage: str
    owner: str
    updated_at: str


class AiInsightResponse(BaseModel):
    title: str
    description: str
    type: Literal["high", "warning", "info"]
    action: str | None = None
    deal_id: str | None = None


class RiskDealInsight(BaseModel):
    id: str
    title: str
    amount: float | None = None
    stage: str
    probability: float | None = None
    updated_at: str


class DashboardAiInsightsResponse(BaseModel):
    summary: str
    insights: list[AiInsightResponse]
    risk_deals: list[RiskDealInsight]
    run_id: str | None = None


class CustomWidgetResponse(BaseModel):
    id: str
    title: str
    enabled: bool = Field(strict=True)


class CustomWidgetSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100, pattern=r"^w-[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=120)
    enabled: bool
