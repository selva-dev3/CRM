from enum import StrEnum

from app.core.errors import ForbiddenError


class UserRole(StrEnum):
    SUPER_ADMIN = "Super Admin"
    ORG_ADMIN = "Organization Admin"
    SALES_MANAGER = "Sales Manager"
    SALES_EXECUTIVE = "Sales Executive"
    MARKETING_EXECUTIVE = "Marketing Executive"
    CUSTOMER_SUPPORT = "Customer Support"


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


async def is_super_admin_user(db, user) -> bool:
    """Whether the given user is a platform super_admin.

    Resolves the user's effective role from ``User.role`` (which may hold a role
    name or a role UUID) before applying the name-based check, so the platform
    super_admin is recognized regardless of how the role was assigned.
    """
    from app.repositories.role_repository import RoleRepository

    role_value = getattr(user, "role", "") or ""
    if is_super_admin_role_name(role_value):
        return True
    if not role_value:
        return False
    role = await RoleRepository().get_role_by_id_or_name(db, role_value)
    return bool(role and is_super_admin_role(role))


def ensure_can_assign_role(*, actor_is_super_admin: bool, target_is_super_admin: bool) -> None:
    """Centralized guard: only a super_admin actor may assign the super_admin role."""
    if target_is_super_admin and not actor_is_super_admin:
        raise ForbiddenError(message="Only super_admin users can assign the super_admin role.")


def check_permission(user_role: str, required_roles: list[UserRole]) -> bool:
    if user_role == UserRole.SUPER_ADMIN:
        return True
    return user_role in [role.value for role in required_roles]
