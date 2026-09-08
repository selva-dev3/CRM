import inspect
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.api.v1.routers import invoices, meetings, quotes, reports, tasks, users
from app.core.rbac_matrix import APPROVED_PERMISSION_KEYS

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PERMISSION_PATTERN = re.compile(r"['\"]([a-z_]+:[a-z_]+)['\"]")
EXPECTED_NON_ROUTER_PERMISSIONS = {
    "activities:create",
    "activities:export",
    "contacts:assign",
    "contacts:bulk_update",
    "dashboard:export",
    "documents:share",
    "projects:assign",
    # Platform authority is enforced by require_platform_admin and cannot be delegated.
    "super_admin:manage",
}


def test_frontend_permission_catalog_matches_backend_catalog() -> None:
    frontend_catalog = REPOSITORY_ROOT / "frontend" / "src" / "lib" / "permissions.ts"
    frontend_keys = set(PERMISSION_PATTERN.findall(frontend_catalog.read_text(encoding="utf-8")))

    assert frontend_keys == set(APPROVED_PERMISSION_KEYS)


def test_backend_permission_dependencies_are_registered() -> None:
    router_root = REPOSITORY_ROOT / "backend" / "app" / "api" / "v1" / "routers"
    used_keys = {
        key
        for router_file in router_root.glob("*.py")
        for key in re.findall(
            r'require_permission\(["\']([a-z_]+:[a-z_]+)["\']\)', router_file.read_text()
        )
    }

    assert used_keys <= set(APPROVED_PERMISSION_KEYS)
    assert "all" not in used_keys
    assert set(APPROVED_PERMISSION_KEYS) - used_keys == EXPECTED_NON_ROUTER_PERMISSIONS


def test_rbac_migration_catalog_matches_runtime_catalog() -> None:
    migration = (
        REPOSITORY_ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "u5e6f7a8b9c0_harden_rbac_integrity.py"
    )
    migration_keys = set(PERMISSION_PATTERN.findall(migration.read_text(encoding="utf-8")))

    assert migration_keys == set(APPROVED_PERMISSION_KEYS)


def _route_permissions(router, path: str, method: str) -> set[str]:
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
    ("router", "path", "method", "permission"),
    [
        (tasks.router, "", "GET", "tasks:read"),
        (tasks.router, "", "POST", "tasks:create"),
        (tasks.router, "/export/csv", "GET", "tasks:export"),
        (tasks.router, "/import/csv", "POST", "tasks:import"),
        (meetings.router, "", "GET", "meetings:read"),
        (meetings.router, "/export/ical", "GET", "meetings:export"),
        (quotes.router, "", "GET", "quotes:read"),
        (quotes.router, "", "POST", "quotes:create"),
        (quotes.router, "/export/csv", "GET", "quotes:export"),
        (quotes.router, "/import/csv", "POST", "quotes:import"),
        (invoices.router, "", "GET", "invoices:read"),
        (invoices.router, "", "POST", "invoices:create"),
        (invoices.router, "/export/csv", "GET", "invoices:export"),
        (invoices.router, "/import/csv", "POST", "invoices:import"),
        (reports.router, "/custom-reports/{report_id}", "DELETE", "reports:delete"),
        (
            users.router,
            "/{user_id}/reset-password-admin",
            "POST",
            "users:reset_password",
        ),
    ],
)
def test_sensitive_routes_use_dedicated_permissions(router, path, method, permission) -> None:
    assert permission in _route_permissions(router, path, method)


@pytest.mark.asyncio
@pytest.mark.parametrize("role_change", [False, True])
async def test_user_update_authorizes_role_assignment_only_when_requested(monkeypatch, role_change):
    from unittest.mock import AsyncMock

    from app.core.errors import ForbiddenError
    from app.models import User
    from app.schemas.crm_schemas import UserUpdate

    authorize = AsyncMock(side_effect=ForbiddenError(message="Missing role assignment permission"))
    update = AsyncMock(return_value={"id": "target"})
    monkeypatch.setattr(users, "authorize_permission", authorize)
    monkeypatch.setattr(users.user_service, "update_user", update)
    db = AsyncMock()
    actor = User(id="actor", organization_id="org-1")
    payload = UserUpdate(role="role-1") if role_change else UserUpdate(name="Updated Name")
    if role_change:
        with pytest.raises(ForbiddenError):
            await users.update_user("target", payload, db, actor)
        authorize.assert_awaited_once_with(db, actor, "users:assign_roles")
        update.assert_not_awaited()
    else:
        assert await users.update_user("target", payload, db, actor) == {"id": "target"}
        authorize.assert_not_awaited()
        update.assert_awaited_once()
