from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ReportTypeEnum(StrEnum):
    SALES_PERFORMANCE = "sales-performance"
    PIPELINE_VELOCITY = "pipeline-velocity"
    WIN_LOSS_RATIO = "win-loss-ratio"
    LEAD_ATTRIBUTION = "lead-attribution"
    REP_LEADERBOARD = "rep-leaderboard"
    REVENUE_FORECASTING = "revenue-forecasting"
    ACTIVITY_METRICS = "activity-metrics"
    DEAL_DURATION = "deal-duration"
    CUSTOMER_ACQUISITION_COST = "customer-acquisition-cost"
    CUSTOMER_LIFETIME_VALUE = "customer-lifetime-value"
    CHURN_ANALYSIS = "churn-analysis"
    QUOTA_ATTAINMENT = "quota-attainment"


class ReportFrequencyEnum(StrEnum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"


class CustomReportItem(BaseModel):
    id: str
    name: str
    filters: str | None = "All Accounts"
    metrics_included: list[str] = Field(default_factory=list)
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class CustomReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    filters: str | None = None


class ScheduledReportItem(BaseModel):
    id: str
    report_type: str
    email: str
    frequency: str
    next_run: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ScheduleReportCreate(BaseModel):
    report_type: ReportTypeEnum
    email: EmailStr
    frequency: ReportFrequencyEnum = ReportFrequencyEnum.WEEKLY


class ExportReportRequest(BaseModel):
    report_type: ReportTypeEnum = ReportTypeEnum.SALES_PERFORMANCE


class PdfExportResponse(BaseModel):
    pdf_url: str


class CsvExportResponse(BaseModel):
    csv_url: str
