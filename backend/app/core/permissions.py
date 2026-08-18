from enum import Enum


class UserRole(str, Enum):
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


def check_permission(user_role: str, required_roles: list[UserRole]) -> bool:
    if user_role == UserRole.SUPER_ADMIN:
        return True
    return user_role in [role.value for role in required_roles]
