from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers.invoices import mark_invoice_paid
from app.models import Invoice
from app.schemas.crm_schemas import InvoiceBase
from app.services.integration_service import integration_service


def _make_invoice(**overrides) -> Invoice:
    defaults = {
        "id": "inv-1",
        "organization_id": "org-1",
        "invoice_number": "INV-1001",
        "amount": 1200.0,
        "status": "Unpaid",
        "due_date": datetime(2026, 9, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Invoice(**defaults)


@pytest.mark.asyncio
async def test_mark_invoice_paid_fires_invoice_paid_event(monkeypatch):
    inv = _make_invoice()
    res = MagicMock()
    res.scalars.return_value.first.return_value = inv
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=res)

    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)

    result = await mark_invoice_paid("inv-1", "Bank Transfer", db)

    assert result["status"] == "success"
    assert inv.status == "Paid"
    db.commit.assert_awaited_once()
    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "invoice.paid"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["amount"] == 1200.0
    assert kwargs["data"]["status"] == "Paid"


@pytest.mark.asyncio
async def test_create_invoice_fires_invoice_created_event(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", "inv-new"))

    from app.api.v1.routers import invoices as invoices_router

    monkeypatch.setattr(
        invoices_router, "get_valid_org_id", AsyncMock(return_value="org-1")
    )
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)

    payload = InvoiceBase(
        deal_id="deal-1",
        invoice_number="INV-200",
        amount=900.0,
        status="Draft",
        due_date="2026-09-01",
    )
    result = await invoices_router.create_invoice(payload, db)

    assert result["id"] == "inv-new"
    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "invoice.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["amount"] == 900.0
