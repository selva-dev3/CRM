import inspect
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, patch

import pytest
from fastapi.routing import APIRoute
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
    invitations,
    invoices,
    leads,
    meetings,
    notes,
    notifications,
    organizations,
    payments,
    products,
    projects,
    quotes,
    reports,
    roles,
    settings,
    tasks,
    users,
)
from app.core.errors import ForbiddenError
from app.core.permissions import is_super_admin_user
from app.core.rbac_matrix import APPROVED_PERMISSION_KEYS, SYSTEM_ROLE_PERMISSIONS
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
async def test_api_key_requires_scope_in_addition_to_owner_rbac():
    user = _make_user()
    user._api_key_scopes = {"leads:read"}

    with pytest.raises(ForbiddenError, match="API key is missing required scope"):
        await _run_permission_dependency("deals:read", user, ["deals:read"])


@pytest.mark.asyncio
async def test_api_key_broad_read_scope_does_not_authorize_writes():
    user = _make_user()
    user._api_key_scopes = {"api:read"}

    assert await _run_permission_dependency("deals:read", user, ["deals:read"]) is user
    with pytest.raises(ForbiddenError, match="API key is missing required scope"):
        await _run_permission_dependency("deals:update", user, ["deals:update"])


@pytest.mark.asyncio
async def test_api_key_broad_write_scope_authorizes_rbac_allowed_mutation():
    user = _make_user()
    user._api_key_scopes = {"api:write"}

    assert await _run_permission_dependency("deals:update", user, ["deals:update"]) is user


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
async def test_user_invite_role_assignment_requires_both_permissions():
    """Permission denial happens before role resolution."""
    user = _make_user()
    for required, granted in (
        ("users:invite", ["users:assign_roles"]),
        ("users:assign_roles", ["users:invite"]),
    ):
        with pytest.raises(ForbiddenError):
            await _run_permission_dependency(required, user, granted)

    invite_route = next(
        route
        for route in users.router.routes
        if isinstance(route, APIRoute) and route.path == "/invite"
    )
    closure_values: set[str] = set()
    for dependency in invite_route.dependencies:
        dependency_callable = dependency.dependency
        if dependency_callable is None:
            continue
        closure_values.update(
            cell.cell_contents
            for cell in (dependency_callable.__closure__ or ())
            if isinstance(cell.cell_contents, str)
        )
    assert {"users:invite", "users:assign_roles"}.issubset(closure_values)

    organization_invite_route = next(
        route
        for route in invitations.router.routes
        if isinstance(route, APIRoute)
        and route.path == ""
        and "POST" in (route.methods or set())
    )
    organization_invite_permissions = {
        cell.cell_contents
        for dependency in organization_invite_route.dependencies
        for cell in (dependency.dependency.__closure__ or ())
        if isinstance(cell.cell_contents, str)
    }
    assert {"invitations:create", "users:assign_roles"}.issubset(
        organization_invite_permissions
    )


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
async def test_get_user_permissions_denies_non_platform_super_admin_role():
    """A role name cannot confer non-delegable platform authority."""
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(
        return_value=["deals:read", "roles:update", "super_admin:manage"]
    )
    repo.role_ids_for_user = AsyncMock(return_value=["sys-1"])
    repo.role_ids_by_name = AsyncMock(return_value=[])
    repo.permission_keys_for_roles = AsyncMock(return_value=["super_admin:manage"])
    repo.roles_by_ids = AsyncMock(
        return_value=[type("R", (), {"id": "sys-1", "name": "Super Admin"})()]
    )
    service = AuthService(repository=repo)
    user = _make_user(role="Super Admin")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert keys == []


@pytest.mark.asyncio
async def test_get_user_permissions_denies_non_platform_resolved_super_admin_role():
    """A corrupt global-role mapping fails closed for a tenant principal."""
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(
        return_value=["deals:read", "roles:update", "super_admin:manage"]
    )
    repo.role_ids_for_user = AsyncMock(return_value=["sys-1"])
    repo.role_ids_by_name = AsyncMock(return_value=[])
    repo.permission_keys_for_roles = AsyncMock(return_value=["super_admin:manage"])
    repo.roles_by_ids = AsyncMock(
        return_value=[type("R", (), {"id": "sys-1", "name": "super_admin"})()]
    )
    service = AuthService(repository=repo)
    user = _make_user(role="sys-1")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert keys == []


@pytest.mark.asyncio
async def test_legacy_super_admin_alias_does_not_grant_platform_access():
    repo = AsyncMock()
    repo.all_permission_keys.return_value = ["dashboard:read", "organization:read"]
    repo.role_ids_for_user.return_value = []
    repo.role_ids_by_name.side_effect = lambda _db, name, _org, **_kwargs: (
        ["global-super"] if name == "super admin" else []
    )
    repo.roles_by_ids.return_value = [
        type(
            "R",
            (),
            {"id": "global-super", "name": "Super Admin", "organization_id": None},
        )()
    ]
    service = AuthService(repository=repo)
    user = _make_user(role="super_admin", organization_id="org-1")

    keys = await service.get_user_permissions(AsyncMock(spec=AsyncSession), user)

    assert keys == []
    repo.role_ids_by_name.assert_not_awaited()
    for call in repo.role_ids_by_name.await_args_list:
        assert call.kwargs == {"global_only": True}


@pytest.mark.asyncio
async def test_tenant_super_admin_named_role_does_not_receive_global_access():
    repo = AsyncMock()
    repo.all_permission_keys.return_value = ["dashboard:read", "organization:read"]
    repo.role_ids_for_user.return_value = ["tenant-super"]
    repo.roles_by_ids.return_value = [
        type(
            "R",
            (),
            {"id": "tenant-super", "name": "Super Admin", "organization_id": "org-1"},
        )()
    ]
    repo.permission_keys_for_roles.return_value = ["dashboard:read"]
    service = AuthService(repository=repo)
    user = _make_user(role="00000000-0000-0000-0000-000000000001", organization_id="org-1")

    keys = await service.get_user_permissions(AsyncMock(spec=AsyncSession), user)

    assert keys == ["dashboard:read"]
    repo.all_permission_keys.assert_not_awaited()


@pytest.mark.asyncio
async def test_super_admin_actor_requires_authoritative_platform_flag():
    tenant_user = _make_user(role="super_admin", is_platform_admin=False)
    platform_user = _make_user(role="Super Admin", organization_id=None, is_platform_admin=True)

    assert await is_super_admin_user(AsyncMock(spec=AsyncSession), tenant_user) is False
    assert await is_super_admin_user(AsyncMock(spec=AsyncSession), platform_user) is True


@pytest.mark.asyncio
async def test_get_user_permissions_admin_holding_super_admin_manage_gets_only_assigned():
    """An Admin role holding super_admin:manage must NOT receive implicit all-key access."""
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(return_value=["deals:read", "roles:update"])
    repo.role_ids_for_user = AsyncMock(return_value=["role-1"])
    repo.role_ids_by_name = AsyncMock(return_value=["role-1"])
    repo.permission_keys_for_roles = AsyncMock(return_value=["a:read", "super_admin:manage"])
    repo.roles_by_ids = AsyncMock(return_value=[type("R", (), {"id": "role-1", "name": "Admin"})()])
    service = AuthService(repository=repo)
    user = _make_user(role="Admin")
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert keys == []
    repo.all_permission_keys.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_get_user_permissions_ignores_foreign_role_mapping():
    repo = AsyncMock()
    repo.role_ids_for_user.return_value = ["foreign-role"]
    repo.role_ids_by_name.return_value = []
    repo.roles_by_ids.return_value = []
    service = AuthService(repository=repo)
    user = _make_user(role="foreign-role", organization_id="org-1")

    keys = await service.get_user_permissions(AsyncMock(spec=AsyncSession), user)

    assert keys == []
    repo.roles_by_ids.assert_awaited_once_with(ANY, ["foreign-role"], "org-1")
    repo.permission_keys_for_roles.assert_not_awaited()


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
    invitations,
    invoices,
    leads,
    meetings,
    notes,
    notifications,
    organizations,
    payments,
    products,
    projects,
    quotes,
    reports,
    roles,
    settings,
    tasks,
    users,
]

# Endpoints that legitimately stay permission-free (public token endpoints / self-service).
NO_PERMISSION_PATHS = {
    ("invitations", "GET", "/{token}"),
    ("invitations", "POST", "/{token}/accept"),
    ("invitations", "GET", "/validate/{token}"),
    ("users", "GET", "/me/profile"),
    ("users", "PUT", "/me/profile"),
    ("users", "POST", "/me/avatar"),
    ("organizations", "POST", "/subscription/webhook"),
}


def test_legacy_user_invitation_acceptance_route_is_removed():
    from app.api.v1.routers import users as users_router

    assert not any(
        isinstance(route, APIRoute)
        and route.path == "/accept-invite"
        and "POST" in (route.methods or set())
        for route in users_router.router.routes
    )


def _route_signature(router, route: APIRoute):
    return (router.router.prefix.rstrip("/") + (route.path or "")).replace("//", "/")


def _route_permissions(router, path: str, method: str) -> set[str]:
    route = next(
        item
        for item in router.router.routes
        if isinstance(item, APIRoute)
        and item.path == path
        and method in (item.methods or set())
    )
    return {
        cell.cell_contents
        for dependency in route.dependencies
        for cell in (dependency.dependency.__closure__ or ())
        if isinstance(cell.cell_contents, str)
    }


def test_role_user_access_and_assignment_routes_use_exact_permissions():
    assert _route_permissions(roles, "/users/{user_id}/role", "GET") == {
        "roles:read",
        "users:roles",
    }
    assert _route_permissions(roles, "/users/{user_id}/role", "PUT") == {
        "users:assign_roles"
    }
    assert _route_permissions(roles, "/check-permission", "POST") == {
        "roles:read",
        "users:roles",
    }
    assert _route_permissions(roles, "/{role_id}/users", "GET") == {
        "roles:read",
        "users:read",
    }
    assert _route_permissions(users, "/bulk-delete", "POST") == {"users:delete"}
    assert _route_permissions(users, "/{user_id}", "PUT") == {"users:update"}
    assert 'authorize_permission(db, current_user, "users:assign_roles")' in inspect.getsource(
        users.update_user
    )
    from app.api.v1.routers import auth as auth_router

    assert _route_permissions(auth_router, "/api-keys/{key_id}", "DELETE") == {
        "api_keys:revoke"
    }


def test_role_grant_mutations_require_roles_assign():
    assert "roles:assign" in _route_permissions(roles, "/{role_id}/clone", "POST")
    assert 'authorize_permission(db, current_user, "roles:assign")' in inspect.getsource(
        roles.create_role
    )
    assert 'authorize_permission(db, current_user, "roles:assign")' in inspect.getsource(
        roles.update_role
    )


@pytest.mark.parametrize("router", GATED_ROUTERS, ids=lambda r: r.__name__)
def test_all_routes_have_permission_dependency(router):
    http_routes = [r for r in (router.router.routes or []) if isinstance(r, APIRoute)]
    assert http_routes, f"{router.__name__} has no HTTP routes"
    for route in http_routes:
        methods = route.methods or set()
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            path = _route_signature(router, route)
            if (router.__name__.rsplit(".", 1)[-1], method, path) in NO_PERMISSION_PATHS:
                continue
            if router.__name__.endswith(".organizations") and (method, path) in {
                ("POST", ""),
                ("GET", "/deletions/{operation_id}"),
                ("POST", "/deletions/{operation_id}/retry"),
            }:
                from app.api.v1.deps import require_platform_admin

                assert any(
                    dep.call is require_platform_admin for dep in route.dependant.dependencies
                )
                continue
            dependencies = route.dependencies or []
            dep_names = {
                getattr(d.dependency, "__name__", "")
                for d in dependencies
                if getattr(d, "dependency", None) is not None
            }
            assert "permission_dependency" in dep_names, (
                f"{router.__name__} {method} {path} is missing require_permission"
            )


def test_self_service_auth_endpoints_require_authentication():
    """Own-account endpoints on the auth router must not be public."""
    from app.api.v1.routers import auth as auth_router

    self_service = {
        "/me": {"GET"},
        "/change-password": {"POST"},
        "/2fa/setup": {"POST"},
        "/2fa/verify": {"POST"},
        "/2fa/disable": {"POST"},
        "/sessions": {"GET"},
        "/api-keys": {"GET", "POST"},
    }
    public = {
        "/login",
        "/logout",
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

    for route in auth_router.router.routes or []:
        if not isinstance(route, APIRoute):
            continue
        path = route.path or ""
        methods = route.methods or set()
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            dependant_deps = (
                route.dependant.dependencies or []
                if getattr(route, "dependant", None) is not None
                else []
            )
            func_sigs = [
                getattr(dep.call, "__name__", "")
                for dep in dependant_deps
                if getattr(dep, "call", None) is not None
            ]
            has_auth = "require_user_session" in func_sigs

            if path in self_service:
                assert method in self_service[path], f"{method} {path} not in self_service map"
                assert has_auth, f"{method} {path} should require a human login session"
            elif path in public:
                assert not has_auth, f"{method} {path} should stay public"


@pytest.mark.asyncio
async def test_organization_subscription_passes_for_admin_with_billing_permission():
    """An Admin user with organization:billing permission passes the dependency."""
    admin_user = _make_user(role="Admin")
    result = await _run_permission_dependency(
        "organization:billing",
        admin_user,
        [
            "organization:read",
            "organization:update",
            "organization:billing",
            "organization:branding",
            "organization:domains",
            "organization:audit",
        ],
    )
    assert result is admin_user


@pytest.mark.asyncio
async def test_organization_subscription_raises_forbidden_when_billing_permission_missing():
    """A user lacking organization:billing receives 403 Forbidden."""
    user = _make_user(role="Sales Executive")
    with pytest.raises(ForbiddenError) as excinfo:
        await _run_permission_dependency(
            "organization:billing",
            user,
            ["organization:read", "leads:read"],
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "FORBIDDEN"
    assert "organization:billing" in excinfo.value.message


@pytest.mark.asyncio
async def test_organization_sub_permissions_pass_for_platform_admin():
    """The authoritative platform principal receives the explicit catalog."""
    repo = AsyncMock()
    repo.all_permission_keys = AsyncMock(
        return_value=[
            "organization:read",
            "organization:update",
            "organization:billing",
            "organization:branding",
            "organization:domains",
            "organization:audit",
            "users:create",
        ]
    )
    repo.role_ids_for_user = AsyncMock(return_value=["sa-1"])
    repo.role_ids_by_name = AsyncMock(return_value=[])
    repo.permission_keys_for_roles = AsyncMock(return_value=["super_admin:manage"])
    repo.roles_by_ids = AsyncMock(
        return_value=[type("R", (), {"id": "sa-1", "name": "super_admin"})()]
    )
    service = AuthService(repository=repo)
    user = _make_user(role="Super Admin", organization_id=None, is_platform_admin=True)
    db = AsyncMock(spec=AsyncSession)

    keys = await service.get_user_permissions(db, user)
    assert "organization:billing" in keys
    assert "organization:branding" in keys
    assert "organization:domains" in keys
    assert "organization:audit" in keys
    assert "users:create" in keys


@pytest.mark.asyncio
async def test_api_key_cannot_access_account_or_credential_management():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.deps import get_current_user, require_user_session
    from app.api.v1.routers import auth as auth_router
    from app.db.session import get_db

    user = _make_user()
    user._api_key_scopes = {"leads:read"}
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/auth")
    app.include_router(users.router, prefix="/users")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    # Exercise the real session dependency before endpoint business logic.
    with pytest.raises(ForbiddenError):
        await require_user_session(user)
    for router, names in (
        (auth_router, {"get_current_user_me", "change_password", "setup_2fa", "verify_2fa", "disable_2fa", "list_sessions", "revoke_session", "list_api_keys", "create_api_key", "revoke_api_key"}),
        (users, {"get_my_profile", "update_my_profile", "upload_avatar"}),
    ):
        for route in router.router.routes:
            if isinstance(route, APIRoute) and route.endpoint.__name__ in names:
                assert any(dep.call is require_user_session for dep in route.dependant.dependencies)
    # APIException is deliberately not converted here: its rejection is the result.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with pytest.raises(ForbiddenError):
            await client.get("/auth/sessions")
        with pytest.raises(ForbiddenError):
            await client.put("/users/me/profile", json={"name": "Changed by key"})


@pytest.mark.asyncio
async def test_human_login_session_retains_account_access():
    from app.api.v1.deps import require_user_session

    user = _make_user()
    assert await require_user_session(user) is user



@pytest.mark.asyncio
@pytest.mark.parametrize("permission", sorted(APPROVED_PERMISSION_KEYS))
async def test_each_registered_permission_requires_an_explicit_grant(permission):
    user = _make_user()
    assert await _run_permission_dependency(permission, user, [permission]) is user
    for denied_grants in ([], ["all"]):
        with pytest.raises(ForbiddenError):
            await _run_permission_dependency(permission, user, denied_grants)


@pytest.mark.asyncio
@pytest.mark.parametrize("role_name", sorted(SYSTEM_ROLE_PERMISSIONS))
async def test_each_tenant_system_role_resolves_its_explicit_permission_set(role_name):
    from app.models import Role

    repo = AsyncMock()
    role = Role(id="role-1", name=role_name, organization_id="org-1", is_system_role=True)
    repo.role_ids_for_user.return_value = [role.id]
    repo.roles_by_ids.return_value = [role]
    repo.permission_keys_for_roles.return_value = list(SYSTEM_ROLE_PERMISSIONS[role_name])
    permissions = await AuthService(repository=repo).get_user_permissions(
        AsyncMock(spec=AsyncSession), _make_user(role=role.id)
    )
    assert set(permissions) == SYSTEM_ROLE_PERMISSIONS[role_name]
    repo.roles_by_ids.assert_awaited_once_with(ANY, [role.id], "org-1")
