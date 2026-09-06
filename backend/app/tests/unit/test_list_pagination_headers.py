from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import deals, invoices, payments, quotes, tasks, users
from app.models import User


def _user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="admin@example.com",
        name="Admin",
        role="Admin",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_deal_list_exposes_filtered_total(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    response = Response()
    monkeypatch.setattr(
        deals.organization_service,
        "resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )
    monkeypatch.setattr(
        deals.deal_service,
        "list_deals",
        AsyncMock(return_value=[{"id": "deal-1"}]),
    )
    count = AsyncMock(return_value=31)
    monkeypatch.setattr(deals.deal_service, "count_deals", count)

    result = await deals.list_deals(
        response=response,
        page=2,
        limit=20,
        stage="Proposal",
        search="Acme",
        db=db,
        current_user=_user(),
    )

    assert result == [{"id": "deal-1"}]
    assert response.headers["X-Total-Count"] == "31"
    count.assert_awaited_once_with(db, organization_id="org-1", search="Acme", stage="Proposal")


@pytest.mark.asyncio
async def test_user_list_exposes_filtered_total(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    response = Response()
    monkeypatch.setattr(users.user_service, "list_users", AsyncMock(return_value=[]))
    count = AsyncMock(return_value=7)
    monkeypatch.setattr(users.user_service, "count_users", count)
    current_user = _user()

    await users.list_users(
        response=response,
        page=1,
        limit=15,
        search="alex",
        db=db,
        current_user=current_user,
    )

    assert response.headers["X-Total-Count"] == "7"
    count.assert_awaited_once_with(db, search="alex", current_user=current_user)


@pytest.mark.asyncio
async def test_task_list_exposes_filtered_total(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    response = Response()
    monkeypatch.setattr(
        tasks.organization_service,
        "resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )
    monkeypatch.setattr(tasks.task_service, "list_tasks", AsyncMock(return_value=[]))
    count = AsyncMock(return_value=12)
    monkeypatch.setattr(tasks.task_service, "count_tasks", count)

    await tasks.list_tasks(
        response=response,
        page=1,
        limit=15,
        status="Pending",
        priority="High",
        search="renewal",
        db=db,
        current_user=_user(),
    )

    assert response.headers["X-Total-Count"] == "12"
    count.assert_awaited_once_with(
        db,
        organization_id="org-1",
        status="Pending",
        priority="High",
        search="renewal",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "service_name", "list_name", "count_name", "expected_total"),
    [
        (invoices, "invoice_service", "list_invoices", "count_invoices", 18),
        (quotes, "quote_service", "list_quotes", "count_quotes", 19),
        (payments, "payment_service", "list_payments", "count_payments", 20),
    ],
)
async def test_billing_lists_expose_filtered_total(
    monkeypatch, module, service_name, list_name, count_name, expected_total
):
    db = AsyncMock(spec=AsyncSession)
    response = Response()
    service = getattr(module, service_name)
    resolver = quotes.quote_service if module is quotes else invoices.invoice_service
    monkeypatch.setattr(
        resolver,
        "resolve_organization_id",
        AsyncMock(return_value="org-1"),
    )
    monkeypatch.setattr(service, list_name, AsyncMock(return_value=[]))
    count = AsyncMock(return_value=expected_total)
    monkeypatch.setattr(service, count_name, count)

    kwargs = {
        "response": response,
        "page": 2,
        "limit": 15,
        "status_filter": "Draft",
        "search": "2026",
        "db": db,
        "current_user": _user(),
    }
    if module is payments:
        kwargs["invoice_id"] = "invoice-1"

    await getattr(module, list_name)(**kwargs)

    assert response.headers["X-Total-Count"] == str(expected_total)
    expected = {
        "organization_id": "org-1",
        "status": "Draft",
        "search": "2026",
    }
    if module is payments:
        expected["invoice_id"] = "invoice-1"
    count.assert_awaited_once_with(db, **expected)
