"""The subscription gateway must not leak into manual customer billing."""

import ast
from pathlib import Path

from app.core.config import Settings


def test_subscription_configuration_is_optional_for_application_startup():
    for name in (
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_SUBSCRIPTION_PORTAL_CONFIGURATION_ID",
    ):
        field = Settings.model_fields[name]
        assert not field.is_required()
        assert field.default is None


def test_customer_billing_modules_do_not_depend_on_subscription_gateway():
    app_root = Path(__file__).resolve().parents[2]
    paths = (
        "services/invoice_service.py",
        "services/invoice_delivery_service.py",
        "services/payment_service.py",
        "services/quote_service.py",
        "services/public_invoice_service.py",
        "api/v1/routers/invoices.py",
        "api/v1/routers/payments.py",
        "api/v1/routers/public_quotes.py",
        "api/v1/routers/public_invoices.py",
    )
    for relative_path in paths:
        source = (app_root / relative_path).read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not any(
                "stripe" in module or "subscription_billing" in module for module in modules
            ), relative_path
        assert "stripe-checkout" not in source
        assert "checkout.stripe.com" not in source
