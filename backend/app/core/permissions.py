from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "Super Admin"
    ORG_ADMIN = "Organization Admin"
    SALES_MANAGER = "Sales Manager"
    SALES_EXECUTIVE = "Sales Executive"
    MARKETING_EXECUTIVE = "Marketing Executive"
    CUSTOMER_SUPPORT = "Customer Support"

def check_permission(user_role: str, required_roles: list[UserRole]) -> bool:
    if user_role == UserRole.SUPER_ADMIN:
        return True
    return user_role in [role.value for role in required_roles]
