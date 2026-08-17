from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.api.v1.routers import (
    ai,
    calendar,
    calls,
    companies,
    contacts,
    dashboard,
    deals,
    documents,
    emails,
    integrations,
    invoices,
    leads,
    meetings,
    notes,
    notifications,
    organizations,
    products,
    quotes,
    reports,
    roles,
    settings,
    tasks,
    users,
)
from app.core.errors import ForbiddenError
from app.models import User
from app.services.auth_service import AuthService, auth_service


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed-secret",
        "role": "Sales Manager",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


async def _run_permission_dependency(permission: str, user: User, keys: list[str]):
    """Invoke the dependency returned by require_permission against a fake db + auth_service."""
    dep = require_permission(permission)
    db = AsyncMock(spec=AsyncSession)

    async def fake_get_user_permissions(db, user, resolved_role_name=""):
        return keys

    with patch.object(auth_service, "get_user_permissions", fake_get_user_permissions):
        result = await dep(current_user=user, db=db)
    return result


@pytest.mark.asyncio
async def test_require_permission_passes_when_user_has_key():
    user = _make_user()
    result = await _run_permission_dependency("deals:update", user, ["deals:read", "deals:update"])
    assert result is user


@pytest.mark.asyncio
async def test_require_permission_raises_forbidden_when_missing():
    user = _make_user()
    with pytest.raises(ForbiddenError) as excinfo:
        await _run_permission_dependency("deals:delete", user, ["deals:read", "deals:update"])
    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "FORBIDDEN"
    assert "deals:delete" in excinfo.value.message


@pytest.mark.asyncio
async def test_require_permission_denies_when_user_has_no_grants():
    user = _make_user()
    with pytest.raises(ForbiddenError):
        await _run_permission_dependency("deals:read", user, [])


@pytest.mark.asyncio
async def test_require_permission_resolves_via_get_user_permissions():
    """The dependency must resolve permissions through get_user_permissions (fail-closed)."""
    user = _make_user()
    dep = require_permission("deals:read")
    db = AsyncMock(spec=AsyncSession)

    captured = {}

    async def spy(db, user, resolved_role_name=""):
        captured["user"] = user
        captured["resolved_role_name"] = resolved_role_name
        return []

    with patch.object(auth_service, "get_user_permissions", spy), pytest.raises(ForbiddenError):
        await dep(current_user=user, db=db)
    assert captured["user"] is user


@pytest.mark.asyncio
async def test_get_user_permissions_denies_empty_grants():
    """A user with no mapped roles must NOT be granted all keys (fail closed)."""
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(return_value=["deals:read", "deals:create"])
    repo.role_ids_for_user = AsyncMock(return_value=[])
    repo.role_ids_by_name = AsyncMock(return_value=[])
    service = AuthService(repository=repo)
    user = _make_user(role="Sales Executive")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert keys == []


@pytest.mark.asyncio
async def test_get_user_permissions_grants_all_for_super_admin_permission():
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(return_value=["deals:read", "roles:update"])
    repo.role_ids_for_user = AsyncMock(return_value=["sys-1"])
    repo.role_ids_by_name = AsyncMock(return_value=[])
    repo.permission_keys_for_roles = AsyncMock(return_value=["super_admin:manage"])
    service = AuthService(repository=repo)
    user = _make_user(role="Super Admin")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert set(keys) == {"deals:read", "roles:update", "super_admin:manage"}


@pytest.mark.asyncio
async def test_get_user_permissions_denies_when_resolution_errors():
    """A permission-resolution failure must never grant access (fail closed)."""
    repo = AsyncMock()
    repo.role_ids_for_user = AsyncMock(side_effect=RuntimeError("db down"))
    service = AuthService(repository=repo)
    user = _make_user(role="Sales Executive")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)

    assert keys == []


# --- Wiring test: every endpoint must carry a require_permission dependency ---

GATED_ROUTERS = [
    ai,
    calendar,
    calls,
    companies,
    contacts,
    dashboard,
    deals,
    documents,
    emails,
    integrations,
    invoices,
    leads,
    meetings,
    notes,
    notifications,
    organizations,
    products,
    quotes,
    reports,
    roles,
    settings,
    tasks,
    users,
]

# Endpoints that legitimately stay permission-free (public token endpoints / self-service).
NO_PERMISSION_PATHS = {
    ("invitations", "GET", "/organizations/invitations/{token}"),
    ("invitations", "POST", "/organizations/invitations/{token}/accept"),
    ("invitations", "GET", "/organizations/invitations/validate/{token}"),
    ("users", "GET", "/me/profile"),
    ("users", "PUT", "/me/profile"),
    ("users", "POST", "/me/avatar"),
}


def _route_signature(router, route):
    return (router.router.prefix.rstrip("/") + route.path).replace("//", "/")


@pytest.mark.parametrize("router", GATED_ROUTERS, ids=lambda r: r.__name__)
def test_all_routes_have_permission_dependency(router):
    http_routes = [r for r in router.router.routes if hasattr(r, "methods")]
    assert http_routes, f"{router.__name__} has no HTTP routes"
    for route in http_routes:
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            path = _route_signature(router, route)
            if (router.__name__.rsplit(".", 1)[-1], method, path) in NO_PERMISSION_PATHS:
                continue
            dep_names = {d.dependency.__name__ for d in route.dependencies}
            assert "permission_dependency" in dep_names, (
                f"{router.__name__} {method} {path} is missing require_permission"
            )


def test_self_service_auth_endpoints_require_authentication():
    """Own-account endpoints on the auth router must not be public."""
    from app.api.v1.routers import auth as auth_router

    self_service = {
        "/me": {"GET"},
        "/logout": {"POST"},
        "/change-password": {"POST"},
        "/2fa/setup": {"POST"},
        "/2fa/verify": {"POST"},
        "/2fa/disable": {"POST"},
        "/sessions": {"GET"},
        "/api-keys": {"GET", "POST"},
    }
    public = {
        "/login",
        "/register",
        "/refresh-token",
        "/forgot-password",
        "/reset-password",
        "/oauth/google",
        "/oauth/microsoft",
        "/invitations/{token}",
        "/accept-invite",
        "/magic-link/request",
        "/magic-link/verify",
    }

    for route in auth_router.router.routes:
        if not hasattr(route, "methods"):
            continue
        path = route.path
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            func_sigs = [
                dep.call.__name__
                for dep in route.dependant.dependencies
                if getattr(dep, "call", None) is not None
            ]
            has_auth = "get_current_user" in func_sigs

            if path in self_service:
                assert method in self_service[path], f"{method} {path} not in self_service map"
                assert has_auth, f"{method} {path} should require get_current_user"
            elif path in public:
                assert not has_auth, f"{method} {path} should stay public"
