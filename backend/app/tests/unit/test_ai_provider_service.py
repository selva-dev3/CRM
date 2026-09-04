from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError
from app.models import AIRun, User
from app.repositories.ai_repository import AIRepository
from app.services.ai_provider_service import AIProviderGateway, AIProviderResult
from app.services.ai_runtime_service import AIRuntimeService


class ScoreOutput(BaseModel):
    score: float = Field(ge=0, le=100)


class ResearchOutput(BaseModel):
    summary: str
    sources: list[str] = Field(default_factory=list)


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
        provider="openai",
        model="research-model",
        input_tokens=10,
        output_tokens=5,
        latency_ms=25,
    )
    service = AIRuntimeService(repository=repository, provider_gateway=provider)
    monkeypatch.setattr(
        "app.services.ai_runtime_service.settings.AI_WEB_SEARCH_MODEL", "research-model"
    )

    await service.execute(
        AsyncMock(spec=AsyncSession),
        current_user=_user(),
        feature="company_intelligence",
        system_prompt="system",
        user_prompt="user",
        output_schema=ResearchOutput,
        web_search=True,
    )

    assert repository.create_run.await_args.kwargs["provider"] == "openai"
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
