import pytest

from app.core.errors import APIException, ForbiddenError
from app.schemas.ai import CRMSearchPlan
from app.services.ai_domain_service import AIDomainService


def test_project_plan_supports_budget_and_date_filters() -> None:
    plan = CRMSearchPlan(
        intent="aggregate",
        entity_type="project",
        aggregate="sum",
        aggregate_field="budget",
        filters=[{"field": "completion_percentage", "operator": "gte", "value": 50}],
        date_field="start_date",
        date_range="this_month",
    )

    AIDomainService._validate_search_plan(plan)


def test_project_plan_rejects_unsupported_field() -> None:
    plan = CRMSearchPlan(
        entity_type="project",
        filters=[{"field": "amount", "operator": "gte", "value": 500}],
    )

    with pytest.raises(APIException, match="unsupported CRM fields"):
        AIDomainService._validate_search_plan(plan)


def test_project_search_requires_project_permission() -> None:
    plan = CRMSearchPlan(entity_type="project")

    with pytest.raises(ForbiddenError, match="projects:read"):
        AIDomainService._require_search_permissions(set(), plan)
