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
    FINANCIAL_OVERVIEW = "financial-overview"
    QUOTE_CONVERSION = "quote-conversion"


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
    status: str

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


class FinancialInvoiceStatusRow(BaseModel):
    status: str
    invoice_count: int = Field(ge=0)
    invoice_value: float
    paid_value: float
    outstanding_amount: float


class FinancialOverviewMetrics(BaseModel):
    pipeline_value: float
    booked_value: float
    quote_count: int = Field(ge=0)
    quoted_value: float
    total_quote_value: float
    accepted_quote_value: float
    invoice_count: int = Field(ge=0)
    invoiced_value: float
    invoice_paid_value: float
    outstanding_amount: float
    overdue_amount: float
    payment_count: int = Field(ge=0)
    collected_revenue: float
    currency: str = Field(min_length=3, max_length=3)
    table_rows: list[FinancialInvoiceStatusRow]


class FinancialOverviewResponse(BaseModel):
    report_type: str
    metrics: FinancialOverviewMetrics
    generated_at: str


class QuoteStatusRow(BaseModel):
    status: str
    quote_count: int = Field(ge=0)
    quote_value: float


class QuoteConversionMetrics(BaseModel):
    total_quotes: int = Field(ge=0)
    accepted_quotes: int = Field(ge=0)
    invoiced_quotes: int = Field(ge=0)
    quote_acceptance_rate: float = Field(ge=0, le=100)
    quote_to_invoice_rate: float = Field(ge=0, le=100)
    currency: str = Field(min_length=3, max_length=3)
    table_rows: list[QuoteStatusRow]


class QuoteConversionResponse(BaseModel):
    report_type: str
    metrics: QuoteConversionMetrics
    generated_at: str
