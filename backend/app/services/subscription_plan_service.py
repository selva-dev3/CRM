from datetime import UTC, datetime
from typing import Any

from app.models import Organization, OrganizationSubscription, SubscriptionPlan

FREE_PLAN_SLUG = "free"
DEFAULT_FREE_PLAN_MAX_USERS = 3


def normalized_max_users(plan: SubscriptionPlan) -> int:
    """Return the persisted seat entitlement for a plan."""
    return plan.max_users if plan.max_users is not None else DEFAULT_FREE_PLAN_MAX_USERS


def apply_plan_to_organization(org: Organization, plan: SubscriptionPlan) -> None:
    """Apply only the plan identity and seat entitlement to an organization."""
    org.plan = plan.name
    org.max_users = normalized_max_users(plan)


def free_subscription_data(
    *, organization_id: str, plan: SubscriptionPlan, current_users: int
) -> dict[str, Any]:
    """Return provider-independent subscription values copied from the Free plan row."""
    return {
        "organization_id": organization_id,
        "plan_id": plan.id,
        "status": "active",
        "billing_cycle": plan.billing_cycle,
        "amount": plan.price_monthly,
        "currency": plan.currency,
        "started_at": datetime.now(UTC),
        "auto_renew": False,
        "max_users": normalized_max_users(plan),
        "current_users": current_users,
        "storage_limit_gb": plan.max_storage_gb,
        "storage_used_gb": 0,
        "ai_credits": plan.ai_credits,
    }


def build_free_subscription(
    *, organization_id: str, plan: SubscriptionPlan, current_users: int
) -> OrganizationSubscription:
    return OrganizationSubscription(
        **free_subscription_data(
            organization_id=organization_id, plan=plan, current_users=current_users
        )
    )
