from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ReportTypeEnum(str, Enum):
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


class ReportFrequencyEnum(str, Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"


class CustomReportItem(BaseModel):
    id: str
    name: str
    filters: Optional[str] = "All Accounts"
    metrics_included: List[str] = Field(default_factory=list)
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class CustomReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    filters: Optional[str] = None


class ScheduledReportItem(BaseModel):
    id: str
    report_type: str
    email: str
    frequency: str
    next_run: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScheduleReportCreate(BaseModel):
    report_type: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    frequency: ReportFrequencyEnum = ReportFrequencyEnum.WEEKLY


class ExportReportRequest(BaseModel):
    report_type: str = Field(default="sales-performance", max_length=100)


class PdfExportResponse(BaseModel):
    pdf_url: str


class CsvExportResponse(BaseModel):
    csv_url: str
