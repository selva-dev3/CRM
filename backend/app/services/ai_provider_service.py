import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from time import monotonic
from typing import TypeVar

import httpx
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import get_logger
from app.core.request_context import get_request_id
from app.services.ai_pricing_service import PricingCalculation, ai_model_pricing_registry

logger = get_logger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)
TextDeltaHandler = Callable[[str], Awaitable[None]]
SUSANOOX_BASE_URL = "https://llm.herd.casa/v1"


@dataclass(frozen=True)
class AIProviderResult:
    output: BaseModel
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    usage_available: bool = True
    attempted_models: tuple[str, ...] = ()
    fallback_used: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        return self.pricing.estimated_cost

    @property
    def pricing(self) -> PricingCalculation:
        return ai_model_pricing_registry.calculate(
            provider=self.provider,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


class AIProviderGateway:
    """Single Susanoox provider boundary for validated structured generation."""

    _RETRYABLE_CODES = {
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_CONNECTION_ERROR",
        "AI_MODEL_UNAVAILABLE",
        "AI_PROVIDER_RATE_LIMITED",
        "AI_PROVIDER_UNAVAILABLE",
        "AI_INVALID_RESPONSE",
        "AI_PROVIDER_ERROR",
    }

    @staticmethod
    def has_usable_api_key(value: str | None) -> bool:
        normalized = value.strip().lower() if value else ""
        return bool(normalized and normalized != "your-susanoox-api-key")

    @staticmethod
    def _request_headers() -> dict[str, str]:
        request_id = get_request_id()
        return {"X-Request-ID": request_id} if request_id else {}

    @staticmethod
    def _safe_log_value(value: object, *, max_length: int = 128) -> str:
        if value is None:
            return "-"
        text = str(value)[:max_length]
        if not text or any(not (character.isalnum() or character in "._-") for character in text):
            return "-"
        return text

    @classmethod
    def _provider_error_code(cls, exc: Exception) -> str:
        code = getattr(exc, "status", None) or getattr(exc, "code", None)
        body = getattr(exc, "body", None)
        if not code and isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code") or error.get("type")
            else:
                code = body.get("code") or body.get("type")
        return cls._safe_log_value(code)

    @classmethod
    def _translate_provider_error(
        cls, *, provider: str, model: str, exc: Exception
    ) -> APIException:
        logger.warning(
            "AI provider request failed provider=%s model=%s error_type=%s "
            "upstream_status=%s provider_code=%s provider_request_id=%s",
            cls._safe_log_value(provider),
            cls._safe_log_value(model),
            type(exc).__name__,
            cls._safe_log_value(getattr(exc, "status_code", None)),
            cls._provider_error_code(exc),
            cls._safe_log_value(getattr(exc, "request_id", None)),
        )
        if isinstance(exc, (TimeoutError, httpx.TimeoutException, openai.APITimeoutError)):
            return APIException(
                status_code=504,
                code="AI_PROVIDER_TIMEOUT",
                message="The AI provider timed out.",
            )
        if isinstance(exc, (httpx.RequestError, openai.APIConnectionError)):
            return APIException(
                status_code=502,
                code="AI_PROVIDER_CONNECTION_ERROR",
                message="The AI provider could not be reached.",
            )
        if isinstance(exc, openai.AuthenticationError):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_AUTH_FAILED",
                message="The configured AI provider credentials were rejected.",
            )
        if isinstance(exc, openai.PermissionDeniedError):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_ACCESS_DENIED",
                message="The configured AI provider account cannot access this operation.",
            )
        if isinstance(exc, openai.NotFoundError):
            return APIException(
                status_code=503,
                code="AI_MODEL_UNAVAILABLE",
                message="The configured AI model is unavailable.",
            )
        if isinstance(exc, openai.RateLimitError):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_RATE_LIMITED",
                message="The AI provider is temporarily rate limited.",
            )
        if isinstance(exc, openai.BadRequestError):
            return APIException(
                status_code=502,
                code="AI_PROVIDER_REQUEST_REJECTED",
                message="The AI provider rejected the structured request.",
            )
        if isinstance(exc, openai.InternalServerError):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="The AI provider is temporarily unavailable.",
            )
        return APIException(
            status_code=502,
            code="AI_PROVIDER_ERROR",
            message="The AI provider could not complete the request.",
        )

    @staticmethod
    def _json_text(value: str) -> str:
        text = value.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @staticmethod
    def _validate_output(raw_text: str, output_schema: type[OutputT]) -> OutputT:
        try:
            return output_schema.model_validate(
                json.loads(AIProviderGateway._json_text(raw_text))
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "AI structured output validation failed schema=%s error_type=%s output_chars=%s",
                output_schema.__name__,
                type(exc).__name__,
                len(raw_text),
            )
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned an invalid structured response.",
            ) from exc

    @staticmethod
    def _strict_json_schema(output_schema: type[OutputT]) -> dict[str, object]:
        schema = output_schema.model_json_schema()

        def accepts_null(value: object) -> bool:
            if not isinstance(value, dict):
                return False
            value_type = value.get("type")
            if value_type == "null" or (
                isinstance(value_type, list) and "null" in value_type
            ):
                return True
            alternatives = value.get("anyOf") or value.get("oneOf")
            return isinstance(alternatives, list) and any(
                accepts_null(alternative) for alternative in alternatives
            )

        def normalize(value: object) -> None:
            if isinstance(value, dict):
                if value.get("type") == "object" and isinstance(value.get("properties"), dict):
                    value["additionalProperties"] = False
                    value["required"] = [
                        name
                        for name, property_schema in value["properties"].items()
                        if not accepts_null(property_schema)
                    ]
                for child in value.values():
                    normalize(child)
            elif isinstance(value, list):
                for child in value:
                    normalize(child)

        normalize(schema)
        return schema

    @staticmethod
    def _client() -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=settings.SUSANOOX_AI_KEY,
            base_url=SUSANOOX_BASE_URL,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )

    async def _susanoox_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.SUSANOOX_AI_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Susanoox is not configured with a usable credential.",
            )
        client = self._client()
        started = monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__.lower(),
                        "strict": True,
                        "schema": self._strict_json_schema(output_schema),
                    },
                },
                store=False,
                extra_headers=self._request_headers(),
            )
        finally:
            await client.close()
        choice = response.choices[0] if response.choices else None
        if getattr(choice, "finish_reason", None) == "length":
            raise APIException(
                status_code=502,
                code="AI_OUTPUT_TRUNCATED",
                message="The AI answer was too long. Please request fewer records.",
            )
        message = getattr(choice, "message", None) if choice else None
        raw_text = getattr(message, "content", None) if message else None
        if getattr(message, "refusal", None) or not isinstance(raw_text, str) or not raw_text.strip():
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no valid structured response.",
            )
        usage = response.usage
        return AIProviderResult(
            output=self._validate_output(raw_text, output_schema),
            provider="susanoox",
            model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=int((monotonic() - started) * 1000),
            usage_available=usage is not None and getattr(usage, "prompt_tokens", None) is not None and getattr(usage, "completion_tokens", None) is not None,
        )

    async def _susanoox_generate_streaming(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
        on_text_delta: TextDeltaHandler,
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.SUSANOOX_AI_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Susanoox is not configured with a usable credential.",
            )
        client = self._client()
        started = monotonic()
        raw_parts: list[str] = []
        usage = None
        finish_reason: str | None = None
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__.lower(),
                        "strict": True,
                        "schema": self._strict_json_schema(output_schema),
                    },
                },
                store=False,
                extra_headers=self._request_headers(),
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                usage = getattr(chunk, "usage", None) or usage
                for choice in getattr(chunk, "choices", []) or []:
                    finish_reason = getattr(choice, "finish_reason", None) or finish_reason
                    delta = getattr(getattr(choice, "delta", None), "content", None)
                    if isinstance(delta, str) and delta:
                        raw_parts.append(delta)
                        await on_text_delta(delta)
        finally:
            await client.close()
        raw_text = "".join(raw_parts)
        if finish_reason == "length":
            raise APIException(
                status_code=502,
                code="AI_OUTPUT_TRUNCATED",
                message="The AI answer was too long. Please request fewer records.",
            )
        if not raw_text.strip():
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no valid structured response.",
            )
        return AIProviderResult(
            output=self._validate_output(raw_text, output_schema),
            provider="susanoox",
            model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=int((monotonic() - started) * 1000),
            usage_available=usage is not None and getattr(usage, "prompt_tokens", None) is not None and getattr(usage, "completion_tokens", None) is not None,
        )

    async def _generate_once(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AIProviderResult:
        if provider != "susanoox":
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Only the Susanoox AI provider is supported.",
            )
        try:
            if on_text_delta is not None:
                return await self._susanoox_generate_streaming(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                    on_text_delta=on_text_delta,
                )
            return await self._susanoox_generate(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
        except APIException:
            raise
        except (openai.APIError, httpx.RequestError, TimeoutError) as exc:
            raise self._translate_provider_error(
                provider="susanoox", model=model, exc=exc
            ) from exc

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
        provider: str | None = None,
        model: str | None = None,
        web_search: bool = False,
        on_text_delta: TextDeltaHandler | None = None,
    ) -> AIProviderResult:
        if (provider or "susanoox").lower() != "susanoox":
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Only the Susanoox AI provider is supported.",
            )
        if web_search:
            raise APIException(
                status_code=503,
                code="AI_WEB_RESEARCH_UNAVAILABLE",
                message="Susanoox web research is not configured for this deployment.",
            )
        selected_model = model or settings.AI_MODEL
        candidates = list(dict.fromkeys([selected_model, *settings.susanoox_model_pool]))
        last_error: APIException | None = None
        attempted_models: list[str] = []
        stream_started = False

        async def guarded_delta(delta: str) -> None:
            nonlocal stream_started
            stream_started = True
            if on_text_delta is not None:
                await on_text_delta(delta)

        for candidate_model in candidates:
            attempted_models.append(candidate_model)
            try:
                result = await self._generate_once(
                    provider="susanoox",
                    model=candidate_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                    on_text_delta=guarded_delta if on_text_delta is not None else None,
                )
                return replace(
                    result,
                    attempted_models=tuple(attempted_models),
                    fallback_used=len(attempted_models) > 1,
                )
            except APIException as exc:
                last_error = exc
                if stream_started or exc.code not in self._RETRYABLE_CODES:
                    raise
                if len(attempted_models) < len(candidates):
                    logger.warning(
                        "Susanoox model failed; attempting configured fallback model=%s code=%s",
                        self._safe_log_value(candidate_model),
                        exc.code,
                    )
        if last_error:
            raise last_error
        raise APIException(
            status_code=503,
            code="AI_PROVIDER_UNAVAILABLE",
            message="No Susanoox model is configured.",
        )

    async def transcribe_audio(self, **_kwargs: object) -> AIProviderResult:
        raise APIException(
            status_code=503,
            code="AI_TRANSCRIPTION_UNAVAILABLE",
            message="Audio transcription is unavailable with the configured Susanoox provider.",
        )


ai_provider_gateway = AIProviderGateway()
