import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.v1.routers.ai import _StructuredResponseDeltaExtractor
from app.core.errors import APIException, ForbiddenError
from app.core.request_context import reset_request_id, set_request_id
from app.models import AIRun, User
from app.schemas.ai import CRMSearchPlan
from app.services.ai_pricing_service import AIModelPricingRegistry, PricingStatus
from app.services.ai_privacy_service import AIDataClass, AIDataClassificationService
from app.services.ai_provider_service import AIProviderResult
from app.services.ai_runtime_service import AIRuntimeService
from app.services.ai_tool_registry import AIToolContext, AIToolRegistry


def test_data_classification_centrally_removes_secrets_and_unrequested_pii():
    payload = {
        "id": "lead-1",
        "status": "Qualified",
        "email": "customer@example.com",
        "nested": {
            "refresh_token": "never-leave-crm",
            "phone_number": "+15551234567",
            "amount": 5000,
        },
    }

    minimized = AIDataClassificationService.minimize(payload)

    assert minimized == {
        "id": "lead-1",
        "status": "Qualified",
        "nested": {"amount": 5000},
    }
    assert AIDataClassificationService.classify("oauth_access_token") is AIDataClass.NEVER_EXPORT


def test_data_classification_exports_only_explicitly_allowed_sensitive_fields():
    minimized = AIDataClassificationService.minimize(
        {"email": "customer@example.com", "phone": "+15551234567", "api_key": "secret"},
        allowed_sensitive_fields={"email"},
    )

    assert minimized == {"email": "customer@example.com"}


def test_provider_model_pricing_registry_supports_known_and_unknown(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_pricing_service.settings.AI_MODEL_PRICING_JSON",
        json.dumps(
            {
                "susanoox": {
                    "susanoox-fast": {
                        "input_per_million": 2.0,
                        "output_per_million": 8.0,
                        "effective_date": "2026-09-01",
                        "currency": "USD",
                    },
                    "susanoox-large": {
                        "input_per_million": 3.0,
                        "output_per_million": 15.0,
                        "effective_date": "2026-09-02",
                        "currency": "USD",
                    }
                },
            }
        ),
    )
    registry = AIModelPricingRegistry()

    known = registry.calculate(
        provider="susanoox",
        model="susanoox-fast",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )
    unknown = registry.calculate(
        provider="susanoox", model="unconfigured", input_tokens=100, output_tokens=20
    )
    large = registry.calculate(
        provider="susanoox",
        model="susanoox-large",
        input_tokens=2_000_000,
        output_tokens=200_000,
    )

    assert known.status is PricingStatus.KNOWN
    assert known.estimated_cost == 6.0
    assert known.version == "2026-09-01"
    assert large.status is PricingStatus.KNOWN
    assert large.estimated_cost == 9.0
    assert large.version == "2026-09-02"
    assert unknown.status is PricingStatus.UNKNOWN
    assert unknown.estimated_cost == 0.0
    assert unknown.currency is None


@pytest.mark.parametrize("invalid_price", ["NaN", "Infinity", "-Infinity"])
def test_pricing_registry_rejects_non_finite_prices(monkeypatch, invalid_price):
    monkeypatch.setattr(
        "app.services.ai_pricing_service.settings.AI_MODEL_PRICING_JSON",
        json.dumps({"susanoox": {"susanoox-fast": {
            "input_per_million": invalid_price,
            "output_per_million": 1,
            "effective_date": "2026-09-16",
        }}}),
    )
    result = AIModelPricingRegistry().calculate(
        provider="susanoox", model="susanoox-fast", input_tokens=100, output_tokens=20
    )
    assert result.status is PricingStatus.UNKNOWN


def test_tool_registry_definitions_are_explicit_and_bounded():
    registry = AIToolRegistry(audit_service=AsyncMock())
    definitions = {tool.name: tool for tool in registry.definitions}
    required = {
        "search_leads",
        "get_lead",
        "search_contacts",
        "get_contact",
        "search_companies",
        "get_company",
        "search_deals",
        "get_deal",
        "get_tasks",
        "get_meetings",
        "get_sales_pipeline",
        "get_dashboard_metrics",
    }

    assert required <= definitions.keys()
    for name in required:
        tool = definitions[name]
        assert tool.required_permission
        assert 0 < tool.maximum_result_count <= 50
        assert tool.timeout_seconds > 0
        assert tool.audit_policy == "metadata_only"
        assert callable(tool.executor)


def test_detail_plan_requires_a_record_id():
    with pytest.raises(ValidationError, match="record_id"):
        CRMSearchPlan(intent="detail", entity_type="lead")


@pytest.mark.asyncio
async def test_tool_registry_rejects_missing_permission_before_executor():
    audit = AsyncMock()
    registry = AIToolRegistry(audit_service=audit)
    context = AIToolContext(
        db=AsyncMock(),
        user=User(id="user-1", email="user@example.com", organization_id="org-1"),
        organization_id="org-1",
        permissions=frozenset({"ai:generate"}),
        run=AIRun(
            id="run-1",
            organization_id="org-1",
            user_id="user-1",
            feature="sales_assistant_chat",
            provider="susanoox",
            model_name="susanoox-fast",
        ),
    )

    with pytest.raises(ForbiddenError):
        await registry.execute_plan(
            context,
            CRMSearchPlan(entity_type="lead"),
            fallback=AsyncMock(return_value=[]),
        )

    audit.record_tool_execution.assert_awaited_once()
    assert audit.record_tool_execution.await_args.kwargs["succeeded"] is False
    assert audit.record_tool_execution.await_args.kwargs["error_category"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_registered_simple_product_list_reuses_product_service():
    audit = AsyncMock()
    registry = AIToolRegistry(audit_service=audit)
    context = AIToolContext(
        db=AsyncMock(),
        user=User(id="user-1", email="user@example.com", organization_id="org-1"),
        organization_id="org-1",
        permissions=frozenset({"products:read"}),
        run=AIRun(
            id="run-1",
            organization_id="org-1",
            user_id="user-1",
            feature="sales_assistant_chat",
            provider="susanoox",
            model_name="susanoox-fast",
        ),
    )
    products = AsyncMock()
    products.list_products.return_value = ([{"id": "product-1", "name": "CRM"}], 1)
    registry.__dict__["products"] = products
    fallback = AsyncMock(return_value=[])

    result = await registry.execute_plan(
        context,
        CRMSearchPlan(entity_type="product", limit=10),
        fallback=fallback,
    )

    assert result == [{"id": "product-1", "name": "CRM"}]
    products.list_products.assert_awaited_once()
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_result_fails_closed_when_required_audit_fails():
    audit = AsyncMock()
    audit.record_tool_execution.side_effect = APIException(
        status_code=503, code="AI_AUDIT_UNAVAILABLE", message="audit failed"
    )
    registry = AIToolRegistry(audit_service=audit)
    products = AsyncMock()
    products.list_products.return_value = ([], 0)
    registry.__dict__["products"] = products
    context = AIToolContext(
        db=AsyncMock(),
        user=User(id="user-1", email="user@example.com", organization_id="org-1"),
        organization_id="org-1",
        permissions=frozenset({"products:read"}),
        run=AIRun(
            id="run-1",
            organization_id="org-1",
            user_id="user-1",
            feature="sales_assistant_chat",
            provider="susanoox",
            model_name="susanoox-fast",
        ),
    )

    with pytest.raises(APIException, match="audit failed"):
        await registry.execute_plan(
            context,
            CRMSearchPlan(entity_type="product"),
            fallback=AsyncMock(return_value=[]),
        )


@pytest.mark.asyncio
async def test_runtime_rejects_unknown_susanoox_pricing_before_provider_call(monkeypatch):
    repository = AsyncMock()
    repository.get_global_feature_setting.return_value = None
    repository.get_organization_config.return_value = None
    repository.get_subscription_for_update.return_value = type(
        "Subscription", (), {"status": "active", "ai_credits": -1}
    )()
    repository.monthly_cost.return_value = 0.0
    monkeypatch.setattr("app.services.ai_pricing_service.settings.AI_MODEL_PRICING_JSON", "{}")
    runtime = AIRuntimeService(repository=repository, provider_gateway=AsyncMock())

    with pytest.raises(APIException) as error:
        await runtime._prepare_run(
            AsyncMock(),
            current_user=User(
                id="user-1", email="user@example.com", organization_id="org-1"
            ),
            feature="sales_assistant_plan",
            entity_type=None,
            entity_id=None,
            prompt_version="test",
            prompt_bytes=100,
        )

    assert error.value.code == "AI_PRICING_UNAVAILABLE"
    repository.create_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_applies_central_privacy_policy_at_provider_boundary(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_pricing_service.settings.AI_MODEL_PRICING_JSON",
        json.dumps(
            {
                "susanoox": {
                    "susanoox-fast": {
                        "input_per_million": 1,
                        "output_per_million": 1,
                        "effective_date": "2026-09-16",
                        "currency": "USD",
                    }
                }
            }
        ),
    )
    provider = AsyncMock()
    provider.generate_structured.return_value = AIProviderResult(
        output=CRMSearchPlan(entity_type="lead"),
        provider="susanoox",
        model="susanoox-fast",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1,
    )
    runtime = AIRuntimeService(repository=AsyncMock(), provider_gateway=provider)
    run = AIRun(
        id="run-1",
        organization_id="org-1",
        user_id="user-1",
        feature="sales_assistant_plan",
        provider="susanoox",
        model_name="susanoox-fast",
        reserved_cost_usd=0.01,
    )
    runtime._prepare_run = AsyncMock(return_value=run)  # type: ignore[method-assign]

    await runtime.execute(
        AsyncMock(),
        current_user=User(id="user-1", email="user@example.com", organization_id="org-1"),
        feature="sales_assistant_plan",
        system_prompt="system",
        provider_context={
            "question": "List leads",
            "email": "private@example.com",
            "access_token": "never-export",
            "nested": {"status": "Qualified", "password": "never-export"},
        },
        task_instructions="Plan the request",
        output_schema=CRMSearchPlan,
    )

    sent = provider.generate_structured.await_args.kwargs["user_prompt"]
    assert "List leads" in sent
    assert "Qualified" in sent
    assert "private@example.com" not in sent
    assert "never-export" not in sent
    assert runtime._prepare_run.await_args.kwargs["prompt_bytes"] == (
        len(provider.generate_structured.await_args.kwargs["system_prompt"].encode("utf-8"))
        + len(sent.encode("utf-8"))
    )


def test_missing_provider_usage_retains_cost_reservation():
    run = AIRun(reserved_cost_usd=0.25)
    result = AIProviderResult(
        output=CRMSearchPlan(entity_type="lead"),
        provider="susanoox", model="susanoox-fast",
        input_tokens=0, output_tokens=0, latency_ms=1, usage_available=False,
    )
    AIRuntimeService._complete_success(run, result)
    assert run.pricing_status == "unknown"
    assert run.estimated_cost_usd == 0
    assert run.reserved_cost_usd == 0.25


def test_structured_stream_extractor_handles_chunked_escaped_text():
    extractor = _StructuredResponseDeltaExtractor()

    chunks = [
        '{"response":"Hello ',
        '\\"CRM\\"',
        '\\nworld","evidence":[]}',
    ]

    assert "".join(extractor.feed(chunk) for chunk in chunks) == 'Hello "CRM"\nworld'


def test_request_context_is_resettable():
    token = set_request_id("request-123")
    try:
        from app.core.request_context import get_request_id

        assert get_request_id() == "request-123"
    finally:
        reset_request_id(token)
