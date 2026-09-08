from app.core.errors import ForbiddenError

SUPER_ADMIN_ROLE_NAMES = {"super_admin", "super admin"}


def is_super_admin_role_name(value: str) -> bool:
    """Whether a role name (or user role string) identifies the platform super_admin."""
    return (value or "").strip().lower() in SUPER_ADMIN_ROLE_NAMES


def is_super_admin_role(role) -> bool:
    """Whether a role object is the platform super_admin role, identified by name.

    is_system_role must NOT be used for this: it only marks a role as
    protected/system-managed and must never grant permissions on its own.
    """
    return is_super_admin_role_name(getattr(role, "name", "") or "")


def is_global_super_admin_role(role) -> bool:
    """Whether a role is the protected global platform super_admin role."""
    return is_super_admin_role(role) and getattr(role, "organization_id", None) is None


def effective_organization_id(user) -> str | None:
    """Return the request-authorized tenant context for this principal.

    Only the platform principal may use the transient context populated by the
    authentication dependency. Tenant principals always remain bound to their
    persisted organization membership.
    """
    if getattr(user, "is_platform_admin", False) is True:
        return getattr(user, "_request_organization_id", None)
    return getattr(user, "organization_id", None)


async def is_super_admin_user(db, user) -> bool:
    """Return the authoritative, non-delegable platform-admin flag."""
    del db
    return getattr(user, "is_platform_admin", False) is True


def ensure_can_assign_role(*, actor_is_super_admin: bool, target_is_super_admin: bool) -> None:
    """Platform identity is provisioned once, never assigned through tenant APIs."""
    if target_is_super_admin:
        raise ForbiddenError(message="The platform Super Admin cannot be assigned through user management.")


def ensure_tenant_managed_user(user) -> None:
    """Protect the platform principal independently of email or selected organization."""
    if getattr(user, "is_platform_admin", False) is True:
        raise ForbiddenError(message="The platform Super Admin cannot be managed as an organization user.")
