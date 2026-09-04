import json
from dataclasses import dataclass
from time import monotonic
from typing import TypeVar

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import get_logger
from app.schemas.ai import TranscriptionResponse, TranscriptionSegment

logger = get_logger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)

_PLACEHOLDER_API_KEYS = {
    "your-openai-api-key",
    "your-anthropic-api-key",
}


@dataclass(frozen=True)
class AIProviderResult:
    output: BaseModel
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        input_cost = self.input_tokens * settings.AI_INPUT_COST_PER_MILLION_USD / 1_000_000
        output_cost = self.output_tokens * settings.AI_OUTPUT_COST_PER_MILLION_USD / 1_000_000
        return round(input_cost + output_cost, 8)


class AIProviderGateway:
    """Single provider boundary for validated, structured AI generation."""

    @staticmethod
    def has_usable_api_key(value: str | None) -> bool:
        normalized = value.strip().lower() if value else ""
        return bool(normalized and normalized not in _PLACEHOLDER_API_KEYS)

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
        code = getattr(exc, "code", None)
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
        cls,
        *,
        provider: str,
        model: str,
        exc: Exception,
    ) -> APIException:
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        logger.warning(
            "AI provider request failed provider=%s model=%s error_type=%s "
            "upstream_status=%s provider_code=%s provider_request_id=%s",
            cls._safe_log_value(provider),
            cls._safe_log_value(model),
            type(exc).__name__,
            cls._safe_log_value(status_code),
            cls._provider_error_code(exc),
            cls._safe_log_value(request_id),
        )

        if isinstance(exc, (openai.APITimeoutError, anthropic.APITimeoutError)):
            return APIException(
                status_code=504,
                code="AI_PROVIDER_TIMEOUT",
                message="The AI provider timed out.",
            )
        if isinstance(exc, (openai.AuthenticationError, anthropic.AuthenticationError)):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_AUTH_FAILED",
                message="The configured AI provider credentials were rejected.",
            )
        if isinstance(exc, (openai.PermissionDeniedError, anthropic.PermissionDeniedError)):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_ACCESS_DENIED",
                message="The configured AI provider account cannot access this operation.",
            )
        if isinstance(exc, (openai.NotFoundError, anthropic.NotFoundError)):
            return APIException(
                status_code=503,
                code="AI_MODEL_UNAVAILABLE",
                message="The configured AI model is unavailable.",
            )
        if isinstance(exc, (openai.RateLimitError, anthropic.RateLimitError)):
            return APIException(
                status_code=503,
                code="AI_PROVIDER_RATE_LIMITED",
                message="The AI provider is temporarily rate limited.",
            )
        if isinstance(exc, (openai.APIConnectionError, anthropic.APIConnectionError)):
            return APIException(
                status_code=502,
                code="AI_PROVIDER_CONNECTION_ERROR",
                message="The AI provider could not be reached.",
            )
        if isinstance(exc, (openai.BadRequestError, anthropic.BadRequestError)):
            return APIException(
                status_code=502,
                code="AI_PROVIDER_REQUEST_REJECTED",
                message="The AI provider rejected the structured request.",
            )
        if isinstance(exc, (openai.InternalServerError, anthropic.InternalServerError)):
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
            payload = json.loads(AIProviderGateway._json_text(raw_text))
            return output_schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned an invalid structured response.",
            ) from exc

    async def _openai_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.OPENAI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="OpenAI is not configured with a usable credential.",
            )
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
        started = monotonic()
        response = await client.responses.parse(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            text_format=output_schema,
            temperature=0.2,
        )
        if response.output_parsed is None:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no structured result.",
            )
        usage = response.usage
        return AIProviderResult(
            output=output_schema.model_validate(response.output_parsed),
            provider="openai",
            model=model,
            input_tokens=int(usage.input_tokens if usage else 0),
            output_tokens=int(usage.output_tokens if usage else 0),
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def _openai_generate_grounded(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.OPENAI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_WEB_RESEARCH_UNAVAILABLE",
                message="AI web research is not configured with a usable credential.",
            )
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
        started = monotonic()
        response = await client.responses.parse(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            tools=[{"type": "web_search", "search_context_size": "medium"}],
            tool_choice="required",
            include=["web_search_call.action.sources"],
            text_format=output_schema,
        )
        if response.output_parsed is None:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no structured research result.",
            )

        sources: set[str] = set()
        for item in response.output:
            if getattr(item, "type", None) == "web_search_call":
                for source in getattr(getattr(item, "action", None), "sources", None) or []:
                    if getattr(source, "url", None):
                        sources.add(source.url)
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", []) or []:
                    for annotation in getattr(content, "annotations", []) or []:
                        if getattr(annotation, "type", None) == "url_citation" and getattr(
                            annotation, "url", None
                        ):
                            sources.add(annotation.url)
        output = output_schema.model_validate(response.output_parsed)
        if "sources" in output.__class__.model_fields:
            output = output.model_copy(update={"sources": sorted(sources)})
        usage = response.usage
        return AIProviderResult(
            output=output,
            provider="openai",
            model=model,
            input_tokens=int(usage.input_tokens if usage else 0),
            output_tokens=int(usage.output_tokens if usage else 0),
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def transcribe_audio(
        self,
        *,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.OPENAI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_TRANSCRIPTION_UNAVAILABLE",
                message="The transcription provider is not configured with a usable credential.",
            )
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
        started = monotonic()
        try:
            response = await client.audio.transcriptions.create(
                model=settings.AI_TRANSCRIPTION_MODEL,
                file=(file_name, content, content_type),
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        except openai.APIError as exc:
            raise self._translate_provider_error(
                provider="openai",
                model=settings.AI_TRANSCRIPTION_MODEL,
                exc=exc,
            ) from exc

        segments = [
            TranscriptionSegment(
                speaker=getattr(segment, "speaker", None),
                start_seconds=float(getattr(segment, "start", 0)),
                end_seconds=float(getattr(segment, "end", 0)),
                text=str(getattr(segment, "text", "")),
            )
            for segment in (getattr(response, "segments", None) or [])
        ]
        output = TranscriptionResponse(
            text=str(getattr(response, "text", "")),
            language=getattr(response, "language", None),
            duration_seconds=getattr(response, "duration", None),
            segments=segments,
        )
        return AIProviderResult(
            output=output,
            provider="openai",
            model=settings.AI_TRANSCRIPTION_MODEL,
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def _anthropic_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.ANTHROPIC_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Anthropic is not configured with a usable credential.",
            )
        client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
        started = monotonic()
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return AIProviderResult(
            output=self._validate_output(raw_text, output_schema),
            provider="anthropic",
            model=model,
            input_tokens=int(response.usage.input_tokens),
            output_tokens=int(response.usage.output_tokens),
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def _generate_once(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        try:
            if provider == "openai":
                return await self._openai_generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            if provider == "anthropic":
                return await self._anthropic_generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="The configured AI provider is unsupported.",
            )
        except APIException:
            raise
        except (openai.APIError, anthropic.APIError) as exc:
            raise self._translate_provider_error(
                provider=provider,
                model=model,
                exc=exc,
            ) from exc

    @staticmethod
    def _fallback_candidate(primary_provider: str) -> tuple[str, str] | None:
        if (
            primary_provider == "openai"
            and AIProviderGateway.has_usable_api_key(settings.ANTHROPIC_API_KEY)
            and settings.AI_ANTHROPIC_FALLBACK_MODEL
        ):
            return "anthropic", settings.AI_ANTHROPIC_FALLBACK_MODEL
        if (
            primary_provider == "anthropic"
            and AIProviderGateway.has_usable_api_key(settings.OPENAI_API_KEY)
            and settings.AI_OPENAI_FALLBACK_MODEL
        ):
            return "openai", settings.AI_OPENAI_FALLBACK_MODEL
        return None

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
        provider: str | None = None,
        model: str | None = None,
        web_search: bool = False,
    ) -> AIProviderResult:
        selected_provider = (provider or settings.AI_PROVIDER).lower()
        selected_model = model or settings.AI_MODEL
        if web_search:
            if selected_provider != "openai":
                raise APIException(
                    status_code=503,
                    code="AI_WEB_RESEARCH_UNAVAILABLE",
                    message="The selected provider does not support configured web research.",
                )
            try:
                return await self._openai_generate_grounded(
                    model=selected_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            except APIException:
                raise
            except openai.APIError as exc:
                raise self._translate_provider_error(
                    provider="openai",
                    model=selected_model,
                    exc=exc,
                ) from exc
        candidates = [(selected_provider, selected_model)]
        fallback = self._fallback_candidate(selected_provider)
        if fallback:
            candidates.append(fallback)

        last_error: APIException | None = None
        for candidate_provider, candidate_model in candidates:
            try:
                return await self._generate_once(
                    provider=candidate_provider,
                    model=candidate_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            except APIException as exc:
                last_error = exc
                if candidate_provider != candidates[-1][0]:
                    logger.warning(
                        "AI provider failed; attempting configured fallback from %s to %s",
                        candidate_provider,
                        candidates[-1][0],
                    )

        if last_error:
            raise last_error
        raise APIException(
            status_code=503,
            code="AI_PROVIDER_UNAVAILABLE",
            message="No AI provider is configured.",
        )


ai_provider_gateway = AIProviderGateway()
