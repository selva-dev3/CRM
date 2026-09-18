import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import monotonic

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
from app.core.logging import get_logger
from app.core.permissions import effective_organization_id
from app.core.request_context import get_request_id
from app.models import AIOrganizationConfig, AIRun, User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import TranscriptionResponse
from app.services.ai_pricing_service import PricingStatus, ai_model_pricing_registry
from app.services.ai_privacy_service import ai_data_classification_service
from app.services.ai_provider_service import (
    AIProviderGateway,
    AIProviderResult,
    ai_provider_gateway,
)

logger = get_logger(__name__)


class AIRuntimeService:
    """Enforces tenant, feature, credit, cost, and audit controls around provider calls."""

    def __init__(
        self,
        repository: AIRepository | None = None,
        provider_gateway: AIProviderGateway | None = None,
    ) -> None:
        self.repository = repository or AIRepository()
        self.provider_gateway = provider_gateway or ai_provider_gateway

    async def enabled_configuration(
        self, db: AsyncSession, organization_id: str
    ) -> AIOrganizationConfig | None:
        global_setting = await self.repository.get_global_feature_setting(db)
        if global_setting and global_setting.value.lower() not in {"true", "1", "yes"}:
            raise ForbiddenError(code="AI_FEATURES_DISABLED", message="AI features are disabled.")
        config = await self.repository.get_organization_config(db, organization_id)
        if config and not config.enabled:
            raise ForbiddenError(
                code="AI_FEATURES_DISABLED",
                message="AI features are disabled for this organization.",
            )
        return config

    @staticmethod
    def configured_provider_model(config: AIOrganizationConfig | None) -> tuple[str, str]:
        allowed_models = {settings.AI_MODEL, *settings.susanoox_model_pool}
        configured_model = config.model_name if config and config.model_name else settings.AI_MODEL
        return "susanoox", (
            configured_model if configured_model in allowed_models else settings.AI_MODEL
        )

    async def configuration_readiness(self, db: AsyncSession, organization_id: str) -> str:
        """Configuration snapshot only; live credentials and quotas are checked at execution."""
        try:
            config = await self.enabled_configuration(db, organization_id)
        except ForbiddenError:
            return "DISABLED"
        _, model = self.configured_provider_model(config)
        if not model.strip() or not self.provider_gateway.has_usable_api_key(
            settings.SUSANOOX_AI_KEY
        ):
            return "PROVIDER_UNAVAILABLE"
        return "READY"

    @staticmethod
    def _rate_limit() -> tuple[int, timedelta]:
        try:
            count_text, period = settings.AI_RATE_LIMIT.lower().split("/", maxsplit=1)
            count = int(count_text)
        except (AttributeError, TypeError, ValueError) as exc:
            raise APIException(
                status_code=500,
                code="AI_RATE_LIMIT_INVALID",
                message="The AI rate-limit configuration is invalid.",
            ) from exc
        windows = {
            "second": timedelta(seconds=1),
            "minute": timedelta(minutes=1),
            "hour": timedelta(hours=1),
            "day": timedelta(days=1),
        }
        normalized_period = period.rstrip("s")
        if count < 1 or normalized_period not in windows:
            raise APIException(
                status_code=500,
                code="AI_RATE_LIMIT_INVALID",
                message="The AI rate-limit configuration is invalid.",
            )
        return count, windows[normalized_period]

    async def _prepare_run(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        feature: str,
        entity_type: str | None,
        entity_id: str | None,
        prompt_version: str,
        prompt_bytes: int = 0,
        local: bool = False,
    ) -> AIRun:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="An organization is required to use AI features.")

        organization_config = await self.enabled_configuration(db, organization_id)

        subscription = await self.repository.get_subscription_for_update(db, organization_id)
        if not subscription:
            raise APIException(
                status_code=402,
                code="AI_SUBSCRIPTION_REQUIRED",
                message="An active AI subscription is required.",
            )
        if subscription.status.lower() not in {"active", "trialing"}:
            raise APIException(
                status_code=402,
                code="AI_SUBSCRIPTION_INACTIVE",
                message="The organization subscription is not active.",
            )

        # Cost and rate decisions happen only after the tenant subscription row
        # is locked. Started runs retain a reservation until success/failure.
        monthly_cost = await self.repository.monthly_cost(db, organization_id)
        cost_limit = (
            organization_config.monthly_cost_limit_usd
            if organization_config and organization_config.monthly_cost_limit_usd is not None
            else settings.AI_MONTHLY_COST_LIMIT_USD
        )
        provider, model = self.configured_provider_model(organization_config)
        reservation = 0.0
        pricing_status = "known" if local else "unknown"
        if not local:
            priced_models = list(dict.fromkeys([model, *settings.susanoox_model_pool]))
            reservations = [
                ai_model_pricing_registry.calculate(
                    provider="susanoox",
                    model=candidate,
                    input_tokens=max(1, prompt_bytes),
                    output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
                )
                for candidate in priced_models
            ]
            if any(item.status is PricingStatus.UNKNOWN for item in reservations):
                raise APIException(
                    status_code=503,
                    code="AI_PRICING_UNAVAILABLE",
                    message=(
                        "Susanoox model pricing must be configured before cost-limited AI "
                        "requests can run."
                    ),
                )
            reservation = max(item.estimated_cost for item in reservations)
            pricing_status = "known"
        if cost_limit >= 0 and monthly_cost + reservation > cost_limit:
            raise APIException(
                status_code=429,
                code="AI_COST_LIMIT_REACHED",
                message="The organization AI monthly cost limit has been reached.",
            )

        rate_limit, window = self._rate_limit()
        recent_runs = await self.repository.recent_run_count(
            db, organization_id, datetime.now(UTC) - window
        )
        if recent_runs >= rate_limit:
            raise APIException(
                status_code=429,
                code="AI_RATE_LIMITED",
                message="The organization AI request rate limit has been reached.",
            )
        ai_credits = subscription.ai_credits
        if ai_credits == 0:
            raise APIException(
                status_code=429,
                code="AI_CREDITS_EXHAUSTED",
                message="The organization has no AI credits remaining.",
            )
        if ai_credits is not None and ai_credits > 0:
            subscription.ai_credits = ai_credits - 1

        run = await self.repository.create_run(
            db,
            organization_id=organization_id,
            user_id=current_user.id,
            feature=feature,
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            model_name=model,
            prompt_version=prompt_version,
            status="started",
            request_id=get_request_id(),
            reserved_cost_usd=reservation,
            pricing_status=pricing_status,
        )
        await db.commit()
        return run

    @staticmethod
    def _complete_success(run: AIRun, result: AIProviderResult) -> None:
        reservation = run.reserved_cost_usd
        run.status = "succeeded"
        run.provider = result.provider
        run.model_name = result.model
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.total_tokens = result.total_tokens
        run.estimated_cost_usd = result.estimated_cost_usd if result.usage_available else 0.0
        run.pricing_status = result.pricing.status.value if result.usage_available else "unknown"
        # Unknown provider/model prices remain explicit. Retaining the bounded
        # reservation prevents unknown-cost requests from bypassing admission.
        run.reserved_cost_usd = (
            0.0
            if result.usage_available and result.pricing.status.value == "known"
            else reservation
        )
        run.pricing_version = result.pricing.version if result.usage_available else None
        run.pricing_currency = result.pricing.currency if result.usage_available else None
        run.latency_ms = result.latency_ms
        run.fallback_used = result.fallback_used
        run.attempted_models_json = json.dumps(result.attempted_models)
        run.completed_at = datetime.now(UTC)

    @staticmethod
    def _complete_failure(run: AIRun, exc: APIException) -> None:
        run.status = "failed"
        run.error_code = exc.code
        run.error_message = exc.message[:1000]
        run.reserved_cost_usd = 0.0
        run.completed_at = datetime.now(UTC)

    async def execute(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        feature: str,
        system_prompt: str,
        provider_context: dict[str, object],
        task_instructions: str,
        output_schema: type[BaseModel],
        entity_type: str | None = None,
        entity_id: str | None = None,
        prompt_version: str = "v1",
        web_search: bool = False,
        allowed_sensitive_fields: set[str] | frozenset[str] = frozenset(),
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[BaseModel, AIRun]:
        started = monotonic()
        minimized_context = ai_data_classification_service.minimize_for_provider(
            provider_context,
            purpose=feature,
            requested_sensitive_fields=allowed_sensitive_fields,
        )
        user_prompt = (
            f"Task instructions:\n{task_instructions}\n\n"
            f"Authorized CRM context:\n{json.dumps(minimized_context, default=str, ensure_ascii=False)}"
        )
        prompt_bytes = len(system_prompt.encode("utf-8")) + len(user_prompt.encode("utf-8"))
        if prompt_bytes > settings.AI_MAX_PROMPT_BYTES:
            raise APIException(
                status_code=413,
                code="AI_PROMPT_TOO_LARGE",
                message="The minimized AI request exceeds the configured provider payload limit.",
            )
        run = await self._prepare_run(
            db,
            current_user=current_user,
            feature=feature,
            entity_type=entity_type,
            entity_id=entity_id,
            prompt_version=prompt_version,
            prompt_bytes=prompt_bytes,
        )
        try:
            result = await self.provider_gateway.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                provider=run.provider,
                model=run.model_name,
                web_search=web_search,
                on_text_delta=on_text_delta,
            )
        except APIException as exc:
            self._complete_failure(run, exc)
            await db.commit()
            raise
        except asyncio.CancelledError:
            run.status = "cancelled"
            run.error_code = "AI_REQUEST_CANCELLED"
            run.error_message = "The AI request was cancelled."
            run.reserved_cost_usd = 0.0
            run.completed_at = datetime.now(UTC)
            await db.commit()
            raise
        self._complete_success(run, result)
        await db.commit()
        logger.info(
            "AI runtime completed feature=%s provider=%s model=%s total_latency_ms=%s",
            feature,
            result.provider,
            result.model,
            int((monotonic() - started) * 1000),
        )
        return result.output, run

    async def execute_transcription(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> tuple[TranscriptionResponse, AIRun]:
        raise APIException(
            status_code=503,
            code="AI_TRANSCRIPTION_UNAVAILABLE",
            message="Audio transcription is unavailable with the configured Susanoox provider.",
        )

    async def start_local_run(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        feature: str,
        entity_type: str | None = None,
    ) -> AIRun:
        run = await self._prepare_run(
            db,
            current_user=current_user,
            feature=feature,
            entity_type=entity_type,
            entity_id=None,
            prompt_version="local-v1",
            local=True,
        )
        run.provider = "local"
        run.model_name = "deterministic"
        run.status = "started"
        run.input_tokens = 0
        run.output_tokens = 0
        run.total_tokens = 0
        run.estimated_cost_usd = 0.0
        run.latency_ms = 0
        await db.commit()
        return run

    async def complete_local_run(self, db: AsyncSession, run: AIRun) -> None:
        run.status = "succeeded"
        run.completed_at = datetime.now(UTC)
        await db.commit()


ai_runtime_service = AIRuntimeService()
