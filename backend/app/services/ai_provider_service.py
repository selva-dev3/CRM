import json
from dataclasses import dataclass
from time import monotonic
from typing import TypeVar

import anthropic
import httpx
import openai
from anthropic import AsyncAnthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
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
    "your-gemini-api-key",
    "your-openrouter-api-key",
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
        code = getattr(exc, "status", None) or getattr(exc, "code", None)
        body = getattr(exc, "body", None)
        if not code and isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code") or error.get("type")
            else:
                code = body.get("code") or body.get("type")
        return cls._safe_log_value(code)

    @staticmethod
    def _gemini_error_reason(exc: genai_errors.APIError) -> str:
        details = getattr(exc, "details", None)
        error = details.get("error") if isinstance(details, dict) else None
        entries = error.get("details") if isinstance(error, dict) else None
        if not isinstance(entries, list):
            return ""
        for entry in entries:
            if isinstance(entry, dict) and entry.get("reason"):
                return str(entry["reason"]).upper()
        return ""

    @classmethod
    def _translate_provider_error(
        cls,
        *,
        provider: str,
        model: str,
        exc: Exception,
    ) -> APIException:
        status_code = getattr(exc, "status_code", None)
        if status_code is None and isinstance(exc, genai_errors.APIError):
            status_code = getattr(exc, "code", None)
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

        if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
            return APIException(
                status_code=504,
                code="AI_PROVIDER_TIMEOUT",
                message="The AI provider timed out.",
            )
        if isinstance(exc, httpx.RequestError):
            return APIException(
                status_code=502,
                code="AI_PROVIDER_CONNECTION_ERROR",
                message="The AI provider could not be reached.",
            )
        if isinstance(exc, genai_errors.APIError):
            upstream_status = getattr(exc, "code", None)
            provider_status = str(getattr(exc, "status", "")).upper()
            provider_reason = cls._gemini_error_reason(exc)
            if (
                upstream_status in {401}
                or provider_status
                in {
                    "API_KEY_INVALID",
                    "UNAUTHENTICATED",
                }
                or provider_reason == "API_KEY_INVALID"
            ):
                return APIException(
                    status_code=503,
                    code="AI_PROVIDER_AUTH_FAILED",
                    message="The configured AI provider credentials were rejected.",
                )
            if upstream_status == 403 or provider_status == "PERMISSION_DENIED":
                return APIException(
                    status_code=503,
                    code="AI_PROVIDER_ACCESS_DENIED",
                    message="The configured AI provider account cannot access this operation.",
                )
            if upstream_status == 404 or provider_status == "NOT_FOUND":
                return APIException(
                    status_code=503,
                    code="AI_MODEL_UNAVAILABLE",
                    message="The configured AI model is unavailable.",
                )
            if upstream_status == 429 or provider_status == "RESOURCE_EXHAUSTED":
                return APIException(
                    status_code=503,
                    code="AI_PROVIDER_RATE_LIMITED",
                    message="The AI provider is temporarily rate limited.",
                )
            if upstream_status in {408, 504} or provider_status == "DEADLINE_EXCEEDED":
                return APIException(
                    status_code=504,
                    code="AI_PROVIDER_TIMEOUT",
                    message="The AI provider timed out.",
                )
            if upstream_status and upstream_status >= 500:
                return APIException(
                    status_code=503,
                    code="AI_PROVIDER_UNAVAILABLE",
                    message="The AI provider is temporarily unavailable.",
                )
            if upstream_status == 400:
                return APIException(
                    status_code=502,
                    code="AI_PROVIDER_REQUEST_REJECTED",
                    message="The AI provider rejected the structured request.",
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

    @staticmethod
    def _openrouter_schema(output_schema: type[OutputT]) -> dict[str, object]:
        """Build a strict JSON Schema for OpenRouter structured output."""
        schema = output_schema.model_json_schema()

        def normalize(value: object) -> None:
            if isinstance(value, dict):
                if value.get("type") == "object" and isinstance(value.get("properties"), dict):
                    value["additionalProperties"] = False
                    value["required"] = list(value["properties"])
                for child in value.values():
                    normalize(child)
            elif isinstance(value, list):
                for child in value:
                    normalize(child)

        normalize(schema)
        return schema

    async def _openrouter_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.OPENROUTER_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="OpenRouter is not configured with a usable credential.",
            )
        client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )
        started = monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__.lower(),
                        "strict": True,
                        "schema": self._openrouter_schema(output_schema),
                    },
                },
            )
        finally:
            await client.close()
        message = response.choices[0].message if response.choices else None
        raw_text = getattr(message, "content", None) if message else None
        if not raw_text:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no structured result.",
            )
        usage = response.usage
        result = AIProviderResult(
            output=self._validate_output(raw_text, output_schema),
            provider="openrouter",
            model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=int((monotonic() - started) * 1000),
        )
        logger.info(
            "AI provider request completed provider=openrouter model=%s latency_ms=%s",
            self._safe_log_value(model),
            result.latency_ms,
        )
        return result

    @staticmethod
    def _gemini_client() -> genai.Client:
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=genai_types.HttpOptions(
                timeout=int(settings.AI_REQUEST_TIMEOUT_SECONDS * 1000),
                retry_options=genai_types.HttpRetryOptions(
                    attempts=settings.AI_MAX_RETRIES + 1,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    async def _gemini_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.GEMINI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_PROVIDER_UNAVAILABLE",
                message="Gemini is not configured with a usable credential.",
            )
        client = self._gemini_client()
        started = monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=output_schema,
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        finally:
            await client.aio.aclose()
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            raw_text = getattr(response, "text", None)
            if not raw_text:
                raise APIException(
                    status_code=502,
                    code="AI_INVALID_RESPONSE",
                    message="The AI provider returned no structured result.",
                )
            output = self._validate_output(raw_text, output_schema)
        else:
            try:
                output = output_schema.model_validate(parsed)
            except ValidationError as exc:
                raise APIException(
                    status_code=502,
                    code="AI_INVALID_RESPONSE",
                    message="The AI provider returned an invalid structured response.",
                ) from exc
        usage = getattr(response, "usage_metadata", None)
        return AIProviderResult(
            output=output,
            provider="gemini",
            model=model,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def _gemini_generate_grounded(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[OutputT],
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.GEMINI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_WEB_RESEARCH_UNAVAILABLE",
                message="AI web research is not configured with a usable credential.",
            )
        client = self._gemini_client()
        started = monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=output_schema,
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        finally:
            await client.aio.aclose()
        parsed = getattr(response, "parsed", None)
        raw_text = getattr(response, "text", None)
        if parsed is None and not raw_text:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no structured research result.",
            )
        try:
            output = (
                output_schema.model_validate(parsed)
                if parsed is not None
                else self._validate_output(str(raw_text), output_schema)
            )
        except ValidationError as exc:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned an invalid structured response.",
            ) from exc

        sources: set[str] = set()
        for candidate in getattr(response, "candidates", None) or []:
            metadata = getattr(candidate, "grounding_metadata", None)
            for chunk in getattr(metadata, "grounding_chunks", None) or []:
                url = getattr(getattr(chunk, "web", None), "uri", None)
                if url:
                    sources.add(str(url))
        if "sources" in output.__class__.model_fields:
            output = output.model_copy(update={"sources": sorted(sources)})
        usage = getattr(response, "usage_metadata", None)
        return AIProviderResult(
            output=output,
            provider="gemini",
            model=model,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            latency_ms=int((monotonic() - started) * 1000),
        )

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
        provider: str | None = None,
        model: str | None = None,
    ) -> AIProviderResult:
        selected_provider = (provider or settings.AI_PROVIDER).lower()
        selected_model = model or settings.AI_TRANSCRIPTION_MODEL
        if selected_provider == "gemini":
            try:
                return await self._gemini_transcribe_audio(
                    model=selected_model,
                    content=content,
                    content_type=content_type,
                )
            except APIException:
                raise
            except (
                genai_errors.APIError,
                httpx.RequestError,
                TimeoutError,
            ) as exc:
                raise self._translate_provider_error(
                    provider="gemini",
                    model=selected_model,
                    exc=exc,
                ) from exc
        if selected_provider != "openai":
            raise APIException(
                status_code=503,
                code="AI_TRANSCRIPTION_UNAVAILABLE",
                message="The selected provider does not support configured transcription.",
            )
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
                model=selected_model,
                file=(file_name, content, content_type),
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        except openai.APIError as exc:
            raise self._translate_provider_error(
                provider="openai",
                model=selected_model,
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
            model=selected_model,
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((monotonic() - started) * 1000),
        )

    async def _gemini_transcribe_audio(
        self,
        *,
        model: str,
        content: bytes,
        content_type: str,
    ) -> AIProviderResult:
        if not self.has_usable_api_key(settings.GEMINI_API_KEY):
            raise APIException(
                status_code=503,
                code="AI_TRANSCRIPTION_UNAVAILABLE",
                message="The transcription provider is not configured with a usable credential.",
            )
        client = self._gemini_client()
        started = monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    "Transcribe this audio. Include only timestamps and speaker labels that can "
                    "be determined from the audio; do not invent them.",
                    genai_types.Part.from_bytes(data=content, mime_type=content_type),
                ],
                config=genai_types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=TranscriptionResponse,
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        finally:
            await client.aio.aclose()
        parsed = getattr(response, "parsed", None)
        raw_text = getattr(response, "text", None)
        if parsed is None and not raw_text:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned no transcription response.",
            )
        try:
            output = (
                TranscriptionResponse.model_validate(parsed)
                if parsed is not None
                else self._validate_output(str(raw_text), TranscriptionResponse)
            )
        except ValidationError as exc:
            raise APIException(
                status_code=502,
                code="AI_INVALID_RESPONSE",
                message="The AI provider returned an invalid transcription response.",
            ) from exc
        usage = getattr(response, "usage_metadata", None)
        return AIProviderResult(
            output=output,
            provider="gemini",
            model=model,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
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
            if provider == "openrouter":
                return await self._openrouter_generate(
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
            if provider == "gemini":
                return await self._gemini_generate(
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
        except (
            openai.APIError,
            anthropic.APIError,
            genai_errors.APIError,
            httpx.RequestError,
            TimeoutError,
        ) as exc:
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
        if (
            primary_provider not in {"gemini", "openrouter"}
            and AIProviderGateway.has_usable_api_key(settings.GEMINI_API_KEY)
            and settings.AI_GEMINI_FALLBACK_MODEL
        ):
            return "gemini", settings.AI_GEMINI_FALLBACK_MODEL
        if primary_provider == "gemini":
            if (
                AIProviderGateway.has_usable_api_key(settings.ANTHROPIC_API_KEY)
                and settings.AI_ANTHROPIC_FALLBACK_MODEL
            ):
                return "anthropic", settings.AI_ANTHROPIC_FALLBACK_MODEL
            if (
                AIProviderGateway.has_usable_api_key(settings.OPENAI_API_KEY)
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
            if selected_provider not in {"openai", "gemini"}:
                raise APIException(
                    status_code=503,
                    code="AI_WEB_RESEARCH_UNAVAILABLE",
                    message="The selected provider does not support configured web research.",
                )
            try:
                if selected_provider == "gemini":
                    return await self._gemini_generate_grounded(
                        model=selected_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        output_schema=output_schema,
                    )
                return await self._openai_generate_grounded(
                    model=selected_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_schema=output_schema,
                )
            except APIException:
                raise
            except (
                openai.APIError,
                genai_errors.APIError,
                httpx.RequestError,
                TimeoutError,
            ) as exc:
                raise self._translate_provider_error(
                    provider=selected_provider,
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
