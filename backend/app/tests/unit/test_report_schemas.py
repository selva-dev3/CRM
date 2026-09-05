import pytest
from pydantic import ValidationError

from app.schemas.report_schemas import FinancialOverviewResponse, QuoteConversionResponse


def test_financial_overview_response_validates_authoritative_metrics():
    response = FinancialOverviewResponse.model_validate(
        {
            "report_type": "Financial Overview",
            "generated_at": "2026-09-05",
            "metrics": {
                "pipeline_value": 100,
                "booked_value": 80,
                "quote_count": 1,
                "quoted_value": 70,
                "total_quote_value": 70,
                "accepted_quote_value": 70,
                "invoice_count": 1,
                "invoiced_value": 70,
                "invoice_paid_value": 70,
                "outstanding_amount": 0,
                "overdue_amount": 0,
                "payment_count": 1,
                "collected_revenue": 70,
                "currency": "INR",
                "table_rows": [],
            },
        }
    )

    assert response.metrics.collected_revenue == 70


def test_quote_conversion_response_rejects_invalid_percentage():
    with pytest.raises(ValidationError):
        QuoteConversionResponse.model_validate(
            {
                "report_type": "Quote Conversion",
                "generated_at": "2026-09-05",
                "metrics": {
                    "total_quotes": 1,
                    "accepted_quotes": 1,
                    "invoiced_quotes": 1,
                    "quote_acceptance_rate": 101,
                    "quote_to_invoice_rate": 100,
                    "currency": "INR",
                    "table_rows": [],
                },
            }
        )
