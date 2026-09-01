from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers.invoices import create_invoice, mark_invoice_paid
from app.core.errors import ForbiddenError
from app.models import User
from app.schemas.crm_schemas import InvoiceBase
from app.services.integration_service import integration_service
from app.services.invoice_service import DealNotClosedWonError, invoice_service

TEST_HASH = "test-hash"


def _payload() -> InvoiceBase:
    return InvoiceBase(
        deal_id="deal-1",
        amount=900.0,
        status="Draft",
        due_date="2026-09-01",
    )


def _current_user() -> User:
    return User(
        id="user-1",
        name="Admin",
        email="admin@crm.com",
        hashed_password=TEST_HASH,
        role="Admin",
        organization_id="org-1",
    )


@pytest.fixture(autouse=True)
def patched_notify(monkeypatch):
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())


@pytest.mark.asyncio
async def test_create_invoice_rejects_deal_not_closed_won(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        invoice_service,
        "create_invoice_from_deal",
        AsyncMock(side_effect=DealNotClosedWonError(message="Deal is not Closed Won")),
    )

    with pytest.raises(DealNotClosedWonError):
        await create_invoice(_payload(), db, current_user=_current_user())


@pytest.mark.asyncio
async def test_create_invoice_delegates_to_service_with_deal_id(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    created = {
        "id": "inv-new",
        "invoice_number": "INV-200",
        "deal_id": "deal-1",
        "amount": 900.0,
        "status": "Draft",
        "due_date": "2026-09-01",
        "items": [],
    }
    spy = AsyncMock(return_value=created)
    monkeypatch.setattr(invoice_service, "create_invoice_from_deal", spy)

    result = await create_invoice(_payload(), db, current_user=_current_user())

    assert result["id"] == "inv-new"
    assert result["status"] == "Draft"
    spy.assert_awaited_once()
    args = spy.await_args_list[-1].args
    assert args[1] == "deal-1"


@pytest.mark.asyncio
async def test_mark_invoice_paid_scopes_by_organization(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    resolve = AsyncMock(return_value="org-1")
    mark_paid = AsyncMock(return_value={"id": "inv-1", "status": "Paid"})
    monkeypatch.setattr(invoice_service, "resolve_organization_id", resolve)
    monkeypatch.setattr(invoice_service, "mark_paid", mark_paid)

    result = await mark_invoice_paid("inv-1", "Bank Transfer", db, current_user=_current_user())

    assert result["status"] == "success"
    resolve.assert_awaited_once()
    kwargs = mark_paid.await_args_list[-1].kwargs
    assert kwargs["invoice_id"] == "inv-1"
    assert kwargs["organization_id"] == "org-1"
    assert kwargs["payment_method"] == "Bank Transfer"


@pytest.mark.asyncio
async def test_missing_permission_raises_forbidden(monkeypatch):
    """Route dependencies enforce RBAC keys via require_permission (invoices:create)."""
    from app.api.v1.deps import require_permission

    dependency = require_permission("invoices:create")

    class _MissingKeysUser:
        pass

    async def _no_keys(db, user):
        return []

    import app.services.auth_service as auth_module

    monkeypatch.setattr(auth_module.auth_service, "get_user_permissions", _no_keys)
    with pytest.raises(ForbiddenError):
        await dependency(current_user=_MissingKeysUser(), db=None)
