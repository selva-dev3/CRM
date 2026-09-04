from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError
from app.models import AIRun, User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import CRMSearchPlan
from app.schemas.dashboard import DashboardAiInsightsResponse
from app.services.ai_provider_service import AIProviderGateway, AIProviderResult
from app.services.ai_runtime_service import AIRuntimeService


class ScoreOutput(BaseModel):
    score: float = Field(ge=0, le=100)


class ResearchOutput(BaseModel):
    summary: str
    sources: list[str] = Field(default_factory=list)


@pytest.mark.asyncio
async def test_openrouter_generation_uses_strict_schema_and_validates_output(monkeypatch):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"score":82}'))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))),
        close=AsyncMock(),
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENROUTER_API_KEY", "set")
    monkeypatch.setattr(
        "app.services.ai_provider_service.AsyncOpenAI",
        lambda **kwargs: client,
    )

    result = await AIProviderGateway().generate_structured(
        provider="openrouter",
        model="openrouter/free",
        system_prompt="system",
        user_prompt="user",
        output_schema=ScoreOutput,
    )

    assert result.output == ScoreOutput(score=82)
    assert result.provider == "openrouter"
    assert result.total_tokens == 16
    request = client.chat.completions.create.await_args.kwargs
    assert request["model"] == "openrouter/free"
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["schema"]["required"] == ["score"]
    assert request["extra_body"] == {"provider": {"require_parameters": True}}
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_openrouter_generation_rejects_invalid_structured_output(monkeypatch):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"score":120}'))],
        usage=None,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))),
        close=AsyncMock(),
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENROUTER_API_KEY", "set")
    monkeypatch.setattr("app.services.ai_provider_service.AsyncOpenAI", lambda **kwargs: client)

    with pytest.raises(APIException) as exc_info:
        await AIProviderGateway().generate_structured(
            provider="openrouter",
            model="openrouter/free",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        SimpleNamespace(content=None, refusal="unsupported request"),
        SimpleNamespace(content="", refusal=None),
    ],
)
async def test_openrouter_rejects_refusal_or_empty_content(monkeypatch, message):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="stop")],
        usage=None,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response))),
        close=AsyncMock(),
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENROUTER_API_KEY", "set")
    monkeypatch.setattr("app.services.ai_provider_service.AsyncOpenAI", lambda **kwargs: client)

    with pytest.raises(APIException) as exc_info:
        await AIProviderGateway().generate_structured(
            provider="openrouter",
            model="openrouter/free",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_INVALID_RESPONSE"
    client.close.assert_awaited_once()


def test_openrouter_crm_search_schema_is_strict():
    schema = AIProviderGateway._openrouter_schema(CRMSearchPlan)

    def object_schemas(value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            found = [value] if value.get("type") == "object" else []
            return found + [item for child in value.values() for item in object_schemas(child)]
        if isinstance(value, list):
            return [item for child in value for item in object_schemas(child)]
        return []

    for object_schema in object_schemas(schema):
        assert object_schema["additionalProperties"] is False
        assert object_schema["required"] == list(object_schema["properties"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "status_code", "expected_code"),
    [
        (openai.AuthenticationError, 401, "AI_PROVIDER_AUTH_FAILED"),
        (openai.RateLimitError, 429, "AI_PROVIDER_RATE_LIMITED"),
        (openai.InternalServerError, 503, "AI_PROVIDER_UNAVAILABLE"),
    ],
)
async def test_openrouter_provider_errors_use_application_error_contract(
    monkeypatch, error_type, status_code, expected_code
):
    response = httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    gateway = AIProviderGateway()
    gateway._openrouter_generate = AsyncMock(
        side_effect=error_type("provider error", response=response, body={})
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENROUTER_API_KEY", "set")

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openrouter",
            model="openrouter/free",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_openrouter_timeout_uses_application_error_contract(monkeypatch):
    gateway = AIProviderGateway()
    gateway._openrouter_generate = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENROUTER_API_KEY", "set")

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openrouter",
            model="openrouter/free",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_PROVIDER_TIMEOUT"


def _user(*, organization_id: str | None = "org-1") -> User:
    return User(id="user-1", email="user@example.com", organization_id=organization_id)


def _repository() -> Any:
    repository: Any = AIRepository()
    repository.get_global_feature_setting = AsyncMock(return_value=None)
    repository.get_organization_config = AsyncMock(return_value=None)
    repository.monthly_cost = AsyncMock(return_value=0.0)
    repository.recent_run_count = AsyncMock(return_value=0)
    repository.get_subscription_for_update = AsyncMock(
        return_value=SimpleNamespace(status="active", ai_credits=5)
    )
    repository.create_run = AsyncMock(
        return_value=AIRun(
            id="run-1",
            organization_id="org-1",
            user_id="user-1",
            feature="lead_scoring",
            provider="openai",
            model_name="gpt-4o-mini",
        )
    )
    return repository


def test_provider_rejects_invalid_structured_output():
    with pytest.raises(APIException) as exc_info:
        AIProviderGateway._validate_output('{"score": 120}', ScoreOutput)

    assert exc_info.value.code == "AI_INVALID_RESPONSE"


def test_provider_accepts_json_code_fence():
    result = AIProviderGateway._validate_output('```json\n{"score": 82}\n```', ScoreOutput)

    assert result.score == 82


def test_dashboard_insights_schema_is_compatible_with_gemini_developer_api():
    schema = DashboardAiInsightsResponse.model_json_schema()

    def contains_additional_properties(value: object) -> bool:
        if isinstance(value, dict):
            return "additionalProperties" in value or any(
                contains_additional_properties(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(contains_additional_properties(item) for item in value)
        return False

    assert not contains_additional_properties(schema)


def _gemini_client(response: object) -> tuple[SimpleNamespace, AsyncMock]:
    generate_content = AsyncMock(return_value=response)
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content),
            aclose=AsyncMock(),
        )
    )
    return client, generate_content


@pytest.mark.asyncio
async def test_gemini_generation_uses_configured_model_and_validates_output(monkeypatch):
    response = SimpleNamespace(
        parsed={"score": 82},
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=4),
    )
    client, generate_content = _gemini_client(response)
    monkeypatch.setattr("app.services.ai_provider_service.settings.GEMINI_API_KEY", "set")
    monkeypatch.setattr(AIProviderGateway, "_gemini_client", staticmethod(lambda: client))

    result = await AIProviderGateway().generate_structured(
        provider="gemini",
        model="configured-gemini-model",
        system_prompt="system",
        user_prompt="user",
        output_schema=ScoreOutput,
    )

    assert result.output == ScoreOutput(score=82)
    assert result.provider == "gemini"
    assert result.model == "configured-gemini-model"
    assert result.total_tokens == 16
    assert generate_content.await_args.kwargs["model"] == "configured-gemini-model"
    config = generate_content.await_args.kwargs["config"]
    assert config.response_schema is ScoreOutput
    assert config.response_mime_type == "application/json"
    assert config.automatic_function_calling.disable is True
    client.aio.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_gemini_generation_rejects_invalid_structured_response(monkeypatch):
    response = SimpleNamespace(
        parsed={"score": 120},
        usage_metadata=None,
    )
    client, _ = _gemini_client(response)
    monkeypatch.setattr("app.services.ai_provider_service.settings.GEMINI_API_KEY", "set")
    monkeypatch.setattr(AIProviderGateway, "_gemini_client", staticmethod(lambda: client))

    with pytest.raises(APIException) as exc_info:
        await AIProviderGateway().generate_structured(
            provider="gemini",
            model="configured-gemini-model",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_gemini_grounded_output_uses_provider_grounding_urls(monkeypatch):
    response = SimpleNamespace(
        parsed={"summary": "Grounded result", "sources": ["https://invented.example"]},
        usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=10),
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[
                        SimpleNamespace(web=SimpleNamespace(uri="https://source.example/company"))
                    ]
                )
            )
        ],
    )
    client, generate_content = _gemini_client(response)
    monkeypatch.setattr("app.services.ai_provider_service.settings.GEMINI_API_KEY", "set")
    monkeypatch.setattr(AIProviderGateway, "_gemini_client", staticmethod(lambda: client))

    result = await AIProviderGateway().generate_structured(
        provider="gemini",
        model="configured-research-model",
        system_prompt="system",
        user_prompt="research company",
        output_schema=ResearchOutput,
        web_search=True,
    )

    assert result.output.sources == ["https://source.example/company"]
    assert result.total_tokens == 30
    assert generate_content.await_args.kwargs["model"] == "configured-research-model"
    assert generate_content.await_args.kwargs["config"].tools


@pytest.mark.asyncio
async def test_gemini_transcription_preserves_response_contract(monkeypatch):
    response = SimpleNamespace(
        parsed={
            "text": "Hello customer",
            "language": "en",
            "duration_seconds": 2.5,
            "segments": [
                {
                    "start_seconds": 0,
                    "end_seconds": 2.5,
                    "text": "Hello customer",
                }
            ],
        },
        usage_metadata=SimpleNamespace(prompt_token_count=15, candidates_token_count=5),
    )
    client, generate_content = _gemini_client(response)
    monkeypatch.setattr("app.services.ai_provider_service.settings.GEMINI_API_KEY", "set")
    monkeypatch.setattr(AIProviderGateway, "_gemini_client", staticmethod(lambda: client))

    result = await AIProviderGateway().transcribe_audio(
        file_name="call.mp3",
        content=b"audio bytes",
        content_type="audio/mpeg",
        provider="gemini",
        model="configured-transcription-model",
    )

    assert result.output.text == "Hello customer"
    assert result.output.segments[0].end_seconds == 2.5
    assert result.total_tokens == 20
    assert generate_content.await_args.kwargs["model"] == "configured-transcription-model"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_code", "expected_status"),
    [
        (
            genai_errors.ClientError(
                400,
                {
                    "error": {
                        "status": "INVALID_ARGUMENT",
                        "details": [{"reason": "API_KEY_INVALID"}],
                    }
                },
            ),
            "AI_PROVIDER_AUTH_FAILED",
            503,
        ),
        (
            genai_errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}),
            "AI_PROVIDER_RATE_LIMITED",
            503,
        ),
        (
            genai_errors.ServerError(503, {"error": {"status": "UNAVAILABLE"}}),
            "AI_PROVIDER_UNAVAILABLE",
            503,
        ),
        (TimeoutError(), "AI_PROVIDER_TIMEOUT", 504),
    ],
)
async def test_gemini_provider_failures_use_application_error_contract(
    monkeypatch,
    provider_error,
    expected_code,
    expected_status,
):
    gateway = AIProviderGateway()
    gateway._gemini_generate = AsyncMock(side_effect=provider_error)
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENAI_API_KEY", None)
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="gemini",
            model="configured-gemini-model",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == expected_code
    assert exc_info.value.status_code == expected_status


@pytest.mark.asyncio
async def test_provider_rejects_example_placeholder_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_provider_service.settings.OPENAI_API_KEY",
        "your-openai-api-key",
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)

    with pytest.raises(APIException) as exc_info:
        await AIProviderGateway().generate_structured(
            provider="openai",
            model="gpt-4o-mini",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "AI_PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "upstream_status", "expected_code", "expected_status"),
    [
        (openai.AuthenticationError, 401, "AI_PROVIDER_AUTH_FAILED", 503),
        (openai.PermissionDeniedError, 403, "AI_PROVIDER_ACCESS_DENIED", 503),
        (openai.NotFoundError, 404, "AI_MODEL_UNAVAILABLE", 503),
        (openai.RateLimitError, 429, "AI_PROVIDER_RATE_LIMITED", 503),
        (openai.BadRequestError, 400, "AI_PROVIDER_REQUEST_REJECTED", 502),
        (openai.InternalServerError, 500, "AI_PROVIDER_UNAVAILABLE", 503),
    ],
)
async def test_openai_status_errors_are_classified_and_safely_logged(
    monkeypatch,
    caplog,
    error_type,
    upstream_status,
    expected_code,
    expected_status,
):
    response = httpx.Response(
        upstream_status,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        headers={"x-request-id": "req_safe123"},
    )
    provider_error = error_type(
        "provider message containing sk-secret-value",
        response=response,
        body={"error": {"code": "provider_error_code", "message": "sk-secret-value"}},
    )
    gateway = AIProviderGateway()
    gateway._openai_generate = AsyncMock(side_effect=provider_error)
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openai",
            model="gpt-4o-mini",
            system_prompt="system",
            user_prompt="customer data must not be logged",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.code == expected_code
    assert "upstream_status=" in caplog.text
    assert "provider_code=provider_error_code" in caplog.text
    assert "provider_request_id=req_safe123" in caplog.text
    assert "sk-secret-value" not in caplog.text
    assert "customer data must not be logged" not in caplog.text


@pytest.mark.asyncio
async def test_openai_connection_error_is_classified_without_logging_message(
    monkeypatch,
    caplog,
):
    provider_error = openai.APIConnectionError(
        message="connection failed with sk-secret-value",
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )
    gateway = AIProviderGateway()
    gateway._openai_generate = AsyncMock(side_effect=provider_error)
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openai",
            model="gpt-4o-mini",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "AI_PROVIDER_CONNECTION_ERROR"
    assert "sk-secret-value" not in caplog.text


@pytest.mark.asyncio
async def test_openai_timeout_is_classified(monkeypatch):
    provider_error = openai.APITimeoutError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )
    gateway = AIProviderGateway()
    gateway._openai_generate = AsyncMock(side_effect=provider_error)
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openai",
            model="gpt-4o-mini",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.status_code == 504
    assert exc_info.value.code == "AI_PROVIDER_TIMEOUT"


@pytest.mark.asyncio
async def test_openai_generation_uses_native_structured_output(monkeypatch):
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=ScoreOutput(score=82),
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    monkeypatch.setattr("app.services.ai_provider_service.AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENAI_API_KEY", "set")

    result = await AIProviderGateway().generate_structured(
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="system",
        user_prompt="user",
        output_schema=ScoreOutput,
    )

    assert result.output.score == 82
    assert result.total_tokens == 16
    assert parse.await_args.kwargs["text_format"] is ScoreOutput


@pytest.mark.asyncio
async def test_openai_transcription_maps_real_provider_response(monkeypatch):
    create = AsyncMock(
        return_value=SimpleNamespace(
            text="Hello customer",
            language="en",
            duration=2.5,
            segments=[SimpleNamespace(start=0.0, end=2.5, text="Hello customer")],
        )
    )
    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    monkeypatch.setattr("app.services.ai_provider_service.AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENAI_API_KEY", "set")

    result = await AIProviderGateway().transcribe_audio(
        file_name="call.mp3",
        content=b"audio bytes",
        content_type="audio/mpeg",
        provider="openai",
        model="configured-transcription-model",
    )

    assert result.output.text == "Hello customer"
    assert result.output.segments[0].end_seconds == 2.5
    create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_grounded_output_uses_only_provider_source_urls(monkeypatch):
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=ResearchOutput(
                summary="Grounded result",
                sources=["https://hallucinated.example"],
            ),
            output=[
                SimpleNamespace(
                    type="web_search_call",
                    action=SimpleNamespace(
                        sources=[SimpleNamespace(url="https://source.example/company")]
                    ),
                ),
                SimpleNamespace(
                    type="message",
                    content=[
                        SimpleNamespace(
                            annotations=[
                                SimpleNamespace(
                                    type="url_citation",
                                    url="https://source.example/news",
                                )
                            ]
                        )
                    ],
                ),
            ],
            usage=SimpleNamespace(input_tokens=20, output_tokens=10),
        )
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    monkeypatch.setattr("app.services.ai_provider_service.AsyncOpenAI", lambda **_kwargs: client)
    monkeypatch.setattr("app.services.ai_provider_service.settings.OPENAI_API_KEY", "set")

    result = await AIProviderGateway().generate_structured(
        provider="openai",
        model="gpt-4.1-mini",
        system_prompt="system",
        user_prompt="research company",
        output_schema=ResearchOutput,
        web_search=True,
    )

    assert result.output.sources == [
        "https://source.example/company",
        "https://source.example/news",
    ]
    assert result.total_tokens == 30
    assert parse.await_args.kwargs["tool_choice"] == "required"
    assert parse.await_args.kwargs["include"] == ["web_search_call.action.sources"]


@pytest.mark.asyncio
async def test_grounded_generation_rejects_provider_without_web_search():
    with pytest.raises(APIException) as exc_info:
        await AIProviderGateway().generate_structured(
            provider="anthropic",
            model="claude",
            system_prompt="system",
            user_prompt="research company",
            output_schema=ResearchOutput,
            web_search=True,
        )

    assert exc_info.value.code == "AI_WEB_RESEARCH_UNAVAILABLE"


@pytest.mark.asyncio
async def test_provider_uses_configured_fallback(monkeypatch):
    gateway = AIProviderGateway()
    primary_error = APIException(
        status_code=502,
        code="AI_PROVIDER_ERROR",
        message="Primary failed",
    )
    gateway._generate_once = AsyncMock(
        side_effect=[
            primary_error,
            AIProviderResult(
                output=ScoreOutput(score=81),
                provider="anthropic",
                model="claude-3-5-sonnet-latest",
                input_tokens=10,
                output_tokens=5,
                latency_ms=20,
            ),
        ]
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", "set")
    monkeypatch.setattr(
        "app.services.ai_provider_service.settings.AI_ANTHROPIC_FALLBACK_MODEL",
        "fallback-model",
    )

    result = await gateway.generate_structured(
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="system",
        user_prompt="user",
        output_schema=ScoreOutput,
    )

    assert result.provider == "anthropic"
    assert gateway._generate_once.await_count == 2


@pytest.mark.asyncio
async def test_provider_preserves_error_when_no_fallback_is_configured(monkeypatch):
    gateway = AIProviderGateway()
    gateway._generate_once = AsyncMock(
        side_effect=APIException(
            status_code=502,
            code="AI_PROVIDER_ERROR",
            message="Primary failed",
        )
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(
        "app.services.ai_provider_service.settings.AI_ANTHROPIC_FALLBACK_MODEL", None
    )

    with pytest.raises(APIException) as exc_info:
        await gateway.generate_structured(
            provider="openai",
            model="gpt-4o-mini",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_PROVIDER_ERROR"
    gateway._generate_once.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_rejects_user_without_organization():
    service = AIRuntimeService(repository=_repository(), provider_gateway=AsyncMock())

    with pytest.raises(ForbiddenError):
        await service.execute(
            AsyncMock(spec=AsyncSession),
            current_user=_user(organization_id=None),
            feature="lead_scoring",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )


@pytest.mark.asyncio
async def test_runtime_overrides_stale_gemini_org_config_for_crm_search(monkeypatch):
    repository = _repository()
    repository.get_organization_config.return_value = SimpleNamespace(
        enabled=True,
        provider="gemini",
        model_name="old-gemini-model",
        monthly_cost_limit_usd=None,
    )
    monkeypatch.setattr("app.services.ai_runtime_service.settings.AI_MODEL", "openrouter/free")
    service = AIRuntimeService(repository=repository, provider_gateway=AsyncMock())

    await service._prepare_run(
        AsyncMock(spec=AsyncSession),
        current_user=_user(),
        feature="crm_search",
        entity_type=None,
        entity_id=None,
        prompt_version="v1",
        provider_override="openrouter",
    )

    kwargs = repository.create_run.await_args.kwargs
    assert kwargs["provider"] == "openrouter"
    assert kwargs["model_name"] == "openrouter/free"


@pytest.mark.asyncio
async def test_runtime_enforces_ai_credits_before_provider_call():
    repository = _repository()
    repository.get_subscription_for_update.return_value.ai_credits = 0
    provider = AsyncMock()
    service = AIRuntimeService(repository=repository, provider_gateway=provider)

    with pytest.raises(APIException) as exc_info:
        await service.execute(
            AsyncMock(spec=AsyncSession),
            current_user=_user(),
            feature="lead_scoring",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_CREDITS_EXHAUSTED"
    provider.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_enforces_organization_rate_limit_before_provider_call(
    monkeypatch,
):
    repository = _repository()
    repository.recent_run_count.return_value = 2
    provider = AsyncMock()
    service = AIRuntimeService(repository=repository, provider_gateway=provider)
    monkeypatch.setattr("app.services.ai_runtime_service.settings.AI_RATE_LIMIT", "2/minute")

    with pytest.raises(APIException) as exc_info:
        await service.execute(
            AsyncMock(spec=AsyncSession),
            current_user=_user(),
            feature="lead_scoring",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    assert exc_info.value.code == "AI_RATE_LIMITED"
    provider.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_tracks_success_and_consumes_one_credit():
    repository = _repository()
    subscription = repository.get_subscription_for_update.return_value
    provider = AsyncMock()
    provider.generate_structured.return_value = AIProviderResult(
        output=ScoreOutput(score=88),
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=100,
        output_tokens=20,
        latency_ms=50,
    )
    service = AIRuntimeService(repository=repository, provider_gateway=provider)
    db = AsyncMock(spec=AsyncSession)

    output, run = await service.execute(
        db,
        current_user=_user(),
        feature="lead_scoring",
        system_prompt="system",
        user_prompt="user",
        output_schema=ScoreOutput,
        entity_type="lead",
        entity_id="lead-1",
    )

    assert output.score == 88
    assert subscription.ai_credits == 4
    assert run.status == "succeeded"
    assert run.total_tokens == 120
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_runtime_uses_dedicated_grounded_research_model(monkeypatch):
    repository = _repository()
    provider = AsyncMock()
    provider.generate_structured.return_value = AIProviderResult(
        output=ResearchOutput(summary="Grounded", sources=["https://source.example"]),
        provider="gemini",
        model="research-model",
        input_tokens=10,
        output_tokens=5,
        latency_ms=25,
    )
    service = AIRuntimeService(repository=repository, provider_gateway=provider)
    monkeypatch.setattr(
        "app.services.ai_runtime_service.settings.AI_GEMINI_WEB_SEARCH_MODEL",
        "research-model",
    )
    monkeypatch.setattr("app.services.ai_runtime_service.settings.AI_PROVIDER", "gemini")

    await service.execute(
        AsyncMock(spec=AsyncSession),
        current_user=_user(),
        feature="company_intelligence",
        system_prompt="system",
        user_prompt="user",
        output_schema=ResearchOutput,
        web_search=True,
    )

    assert repository.create_run.await_args.kwargs["provider"] == "gemini"
    assert repository.create_run.await_args.kwargs["model_name"] == "research-model"
    assert provider.generate_structured.await_args.kwargs["web_search"] is True


@pytest.mark.asyncio
async def test_runtime_audits_provider_failure_without_fabricating_result():
    repository = _repository()
    provider = AsyncMock()
    provider.generate_structured.side_effect = APIException(
        status_code=502,
        code="AI_PROVIDER_ERROR",
        message="Provider failed",
    )
    service = AIRuntimeService(repository=repository, provider_gateway=provider)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.execute(
            db,
            current_user=_user(),
            feature="lead_scoring",
            system_prompt="system",
            user_prompt="user",
            output_schema=ScoreOutput,
        )

    run = repository.create_run.return_value
    assert exc_info.value.code == "AI_PROVIDER_ERROR"
    assert run.status == "failed"
    assert run.error_code == "AI_PROVIDER_ERROR"
    assert db.commit.await_count == 2
