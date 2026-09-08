import inspect
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import calls, contacts, leads
from app.models import User
from app.schemas.crm_schemas import CallLogBase


def _required_permission(route: APIRoute) -> str | None:
    for dependency in route.dependencies:
        call = dependency.dependency
        if getattr(call, "__name__", "") == "permission_dependency":
            return inspect.getclosurevars(call).nonlocals["permission"]
    return None


@pytest.mark.parametrize(
    ("router", "path", "method", "permission"),
    [
        (leads.router, "/{lead_id}/calls", "GET", "calls:read"),
        (leads.router, "/{lead_id}/calls", "POST", "calls:create"),
        (contacts.router, "/{contact_id}/calls", "GET", "calls:read"),
        (calls.router, "/{call_id}", "PUT", "calls:update"),
        (calls.router, "/{call_id}", "DELETE", "calls:delete"),
    ],
)
def test_call_routes_use_call_permissions(router, path, method, permission):
    route = next(
        candidate
        for candidate in router.routes
        if isinstance(candidate, APIRoute)
        and candidate.path == path
        and method in (candidate.methods or set())
    )

    assert _required_permission(route) == permission


@pytest.mark.asyncio
async def test_lead_create_route_uses_path_lead_and_shared_call_service(monkeypatch):
    service_call = AsyncMock(return_value={"id": "call-1"})
    monkeypatch.setattr(leads.call_service, "log_call", service_call)
    db = AsyncMock(spec=AsyncSession)
    user = User(id="user-1", email="user@crm.com", organization_id="org-1")
    payload = CallLogBase(
        lead_id="manipulated-lead",
        contact_id="contact-1",
        company_id="company-1",
        deal_id="deal-1",
    )

    await leads.log_lead_call(
        lead_id="path-lead",
        payload=payload,
        idempotency_key="request-1",
        db=db,
        current_user=user,
    )

    forwarded = service_call.await_args.args[1]
    assert forwarded.lead_id == "path-lead"
    assert forwarded.contact_id == "contact-1"
    assert forwarded.company_id == "company-1"
    assert forwarded.deal_id == "deal-1"
    assert service_call.await_args.kwargs["idempotency_key"] == "request-1"
