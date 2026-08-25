from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import quotes
from app.core.errors import NotFoundError
from app.models import User
from app.schemas.crm_schemas import BulkDeleteRequest
from app.services.quote_service import quote_service


def make_user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="rep@example.com",
        name="Rep",
        role="Sales Executive",
        is_active=True,
    )


ACTION_CASES = [
    ("send_quote_email", "send_quote", {"recipient_email": "buyer@example.com"}),
    ("accept_quote", "accept_quote", {}),
    ("reject_quote", "reject_quote", {"reason": "Budget constraints"}),
    ("get_quote_pdf", "get_quote_pdf", {}),
    ("convert_quote_to_invoice", "convert_quote_to_invoice", {}),
    ("create_quote_revision", "create_quote_revision", {}),
    ("get_quote_revisions", "get_quote_revisions", {}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("route_name", "service_name", "extra"), ACTION_CASES)
async def test_quote_action_routes_resolve_org_and_delegate(
    monkeypatch, route_name, service_name, extra
):
    db = AsyncMock(spec=AsyncSession)
    user = make_user()
    resolve = AsyncMock(return_value="org-1")
    action = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(quote_service, "resolve_organization_id", resolve)
    monkeypatch.setattr(quote_service, service_name, action)

    await getattr(quotes, route_name)("quote-1", db=db, current_user=user, **extra)

    resolve.assert_awaited_once_with(db, user)
    assert action.await_args.kwargs["quote_id"] == "quote-1"
    assert action.await_args.kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(("route_name", "service_name", "extra"), ACTION_CASES)
@pytest.mark.parametrize("quote_id", ["foreign", "missing"])
async def test_quote_action_routes_preserve_cross_tenant_and_missing_not_found(
    monkeypatch, route_name, service_name, extra, quote_id
):
    db = AsyncMock(spec=AsyncSession)
    user = make_user()
    monkeypatch.setattr(
        quote_service,
        "resolve_organization_id",
        AsyncMock(return_value="org-1"),
    )
    action = AsyncMock(side_effect=NotFoundError(message="Quote 'foreign' not found"))
    monkeypatch.setattr(quote_service, service_name, action)

    with pytest.raises(NotFoundError):
        await getattr(quotes, route_name)(quote_id, db=db, current_user=user, **extra)

    assert action.await_args.kwargs["quote_id"] == quote_id
    assert action.await_args.kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_bulk_delete_route_is_scoped_and_preserves_response(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    user = make_user()
    resolve = AsyncMock(return_value="org-1")
    bulk_delete = AsyncMock(
        return_value={"affected_count": 1, "message": "Quotes deleted successfully"}
    )
    monkeypatch.setattr(quote_service, "resolve_organization_id", resolve)
    monkeypatch.setattr(quote_service, "bulk_delete_quotes", bulk_delete)

    result = await quotes.bulk_delete_quotes(
        BulkDeleteRequest(ids=["quote-1", "foreign-quote"]),
        db=db,
        current_user=user,
    )

    assert result["affected_count"] == 1
    bulk_delete.assert_awaited_once_with(
        db,
        quote_ids=["quote-1", "foreign-quote"],
        organization_id="org-1",
    )
