import inspect

import pytest
from fastapi.routing import APIRoute

from app.api.v1.routers import companies, contacts, deals, leads, quotes


def _permissions(router, path: str, method: str) -> set[str]:
    route = next(
        item
        for item in router.routes
        if isinstance(item, APIRoute) and item.path == path and method in (item.methods or set())
    )
    return {
        inspect.getclosurevars(dependency.dependency).nonlocals["permission"]
        for dependency in route.dependencies
        if getattr(dependency.dependency, "__name__", "") == "permission_dependency"
    }


@pytest.mark.parametrize(
    ("router", "path", "method", "expected"),
    [
        (companies.router, "/{company_id}/contacts", "GET", {"companies:read", "contacts:read"}),
        (companies.router, "/{company_id}/deals", "GET", {"companies:read", "deals:read"}),
        (companies.router, "/{company_id}/quotes", "GET", {"companies:read", "quotes:read"}),
        (companies.router, "/{company_id}/invoices", "GET", {"companies:read", "invoices:read"}),
        (companies.router, "/{company_id}/documents", "GET", {"companies:read", "documents:read"}),
        (contacts.router, "/{contact_id}/deals", "GET", {"contacts:read", "deals:read"}),
        (contacts.router, "/{contact_id}/activities", "GET", {"contacts:read", "activities:read"}),
        (contacts.router, "/{contact_id}/notes", "POST", {"contacts:read", "notes:create"}),
        (contacts.router, "/{contact_id}/calls", "GET", {"contacts:read", "calls:read"}),
        (deals.router, "/{deal_id}/products", "GET", {"deals:read", "products:read"}),
        (deals.router, "/{deal_id}/notes", "POST", {"deals:read", "notes:create"}),
        (deals.router, "/{deal_id}/quotes", "GET", {"deals:read", "quotes:read"}),
        (deals.router, "/{deal_id}/invoice", "POST", {"deals:read", "invoices:create"}),
        (leads.router, "/{lead_id}/documents", "GET", {"leads:read", "documents:read"}),
        (leads.router, "/{lead_id}/documents", "POST", {"leads:read", "documents:upload"}),
        (leads.router, "/{lead_id}/notes", "POST", {"leads:read", "notes:create"}),
        (leads.router, "/{lead_id}/tasks", "POST", {"leads:read", "tasks:create"}),
        (leads.router, "/{lead_id}/calls", "POST", {"leads:read", "calls:create"}),
        (
            quotes.router,
            "/{quote_id}/convert-to-invoice",
            "POST",
            {"quotes:read", "invoices:create"},
        ),
    ],
)
def test_nested_routes_require_parent_and_child_permissions(
    router, path: str, method: str, expected: set[str]
) -> None:
    assert _permissions(router, path, method) == expected
