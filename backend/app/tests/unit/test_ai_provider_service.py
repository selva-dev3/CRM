from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.core.errors import APIException
from app.services.ai_provider_service import AIProviderGateway


class ResultSchema(BaseModel):
    response: str


class _AsyncChunks:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._chunks)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _client(response):
    create = AsyncMock(return_value=response)
    close = AsyncMock()
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=close,
    )


@pytest.mark.asyncio
async def test_susanoox_structured_request_is_privacy_disabled(monkeypatch):
    client = _client(
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"response":"ok"}', refusal=None))],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
        )
    )
    monkeypatch.setattr("app.services.ai_provider_service.settings.SUSANOOX_AI_KEY", "test-key")
    monkeypatch.setattr(AIProviderGateway, "_client", staticmethod(lambda: client))

    result = await AIProviderGateway().generate_structured(
        system_prompt="system",
        user_prompt="user",
        output_schema=ResultSchema,
        provider="susanoox",
        model="susanoox-fast",
    )

    assert result.output == ResultSchema(response="ok")
    kwargs = client.chat.completions.create.await_args.kwargs
    assert kwargs["store"] is False
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert result.usage_available is True
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_susanoox_missing_usage_is_not_treated_as_zero_cost(monkeypatch):
    client = _client(SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"response":"ok"}', refusal=None))],
        usage=None,
    ))
    monkeypatch.setattr("app.services.ai_provider_service.settings.SUSANOOX_AI_KEY", "test-key")
    monkeypatch.setattr(AIProviderGateway, "_client", staticmethod(lambda: client))
    result = await AIProviderGateway().generate_structured(
        system_prompt="system", user_prompt="user", output_schema=ResultSchema,
        provider="susanoox", model="susanoox-fast",
    )
    assert result.usage_available is False


@pytest.mark.asyncio
async def test_susanoox_uses_native_provider_stream(monkeypatch):
    chunks = _AsyncChunks(
        [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content='{"response":"hel'))],
                usage=None,
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content='lo"}'))],
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
            ),
        ]
    )
    client = _client(chunks)
    monkeypatch.setattr("app.services.ai_provider_service.settings.SUSANOOX_AI_KEY", "test-key")
    monkeypatch.setattr(AIProviderGateway, "_client", staticmethod(lambda: client))
    deltas: list[str] = []

    async def on_delta(value: str) -> None:
        deltas.append(value)

    result = await AIProviderGateway().generate_structured(
        system_prompt="system",
        user_prompt="user",
        output_schema=ResultSchema,
        provider="susanoox",
        model="susanoox-fast",
        on_text_delta=on_delta,
    )

    assert result.output == ResultSchema(response="hello")
    assert deltas == ['{"response":"hel', 'lo"}']
    kwargs = client.chat.completions.create.await_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["store"] is False


@pytest.mark.asyncio
async def test_other_providers_are_rejected():
    with pytest.raises(APIException) as error:
        await AIProviderGateway().generate_structured(
            system_prompt="system",
            user_prompt="user",
            output_schema=ResultSchema,
            provider="openai",
        )
    assert error.value.code == "AI_PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_susanoox_web_search_is_explicitly_unavailable():
    with pytest.raises(APIException) as error:
        await AIProviderGateway().generate_structured(
            system_prompt="system",
            user_prompt="user",
            output_schema=ResultSchema,
            provider="susanoox",
            web_search=True,
        )
    assert error.value.code == "AI_WEB_RESEARCH_UNAVAILABLE"


@pytest.mark.asyncio
async def test_no_fallback_after_stream_has_started(monkeypatch):
    gateway = AIProviderGateway()
    calls: list[str] = []

    async def generate_once(**kwargs):
        calls.append(kwargs["model"])
        await kwargs["on_text_delta"]("partial")
        raise APIException(status_code=503, code="AI_PROVIDER_UNAVAILABLE", message="failed")

    monkeypatch.setattr(gateway, "_generate_once", generate_once)
    monkeypatch.setattr("app.services.ai_provider_service.settings.SUSANOOX_MODEL_POOL", "fallback")
    with pytest.raises(APIException):
        await gateway.generate_structured(
            system_prompt="system",
            user_prompt="user",
            output_schema=ResultSchema,
            provider="susanoox",
            model="primary",
            on_text_delta=AsyncMock(),
        )
    assert calls == ["primary"]
