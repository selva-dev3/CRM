from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
from app.core.logging import get_logger
from app.models import AIRun, User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import TranscriptionResponse
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
        provider_override: str | None = None,
        model_override: str | None = None,
        model_overrides: dict[str, str] | None = None,
    ) -> AIRun:
        organization_id = current_user.organization_id
        if not organization_id:
            raise ForbiddenError(message="An organization is required to use AI features.")

        global_setting = await self.repository.get_global_feature_setting(db)
        if global_setting and global_setting.value.lower() not in {"true", "1", "yes"}:
            raise ForbiddenError(
                code="AI_FEATURES_DISABLED",
                message="AI features are disabled for this deployment.",
            )

        organization_config = await self.repository.get_organization_config(db, organization_id)
        if organization_config and not organization_config.enabled:
            raise ForbiddenError(
                code="AI_FEATURES_DISABLED",
                message="AI features are disabled for this organization.",
            )

        monthly_cost = await self.repository.monthly_cost(db, organization_id)
        cost_limit = (
            organization_config.monthly_cost_limit_usd
            if organization_config and organization_config.monthly_cost_limit_usd is not None
            else settings.AI_MONTHLY_COST_LIMIT_USD
        )
        if cost_limit >= 0 and monthly_cost >= cost_limit:
            raise APIException(
                status_code=429,
                code="AI_COST_LIMIT_REACHED",
                message="The organization AI monthly cost limit has been reached.",
            )

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
        if subscription.ai_credits == 0:
            raise APIException(
                status_code=429,
                code="AI_CREDITS_EXHAUSTED",
                message="The organization has no AI credits remaining.",
            )
        if subscription.ai_credits > 0:
            subscription.ai_credits -= 1

        provider = provider_override or (
            organization_config.provider
            if organization_config and organization_config.provider
            else settings.AI_PROVIDER
        )
        configured_model = (
            organization_config.model_name
            if organization_config and organization_config.model_name
            else settings.AI_MODEL
        )
        model = model_override or (model_overrides or {}).get(provider) or configured_model
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
        )
        await db.commit()
        return run

    @staticmethod
    def _complete_success(run: AIRun, result: AIProviderResult) -> None:
        run.status = "succeeded"
        run.provider = result.provider
        run.model_name = result.model
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.total_tokens = result.total_tokens
        run.estimated_cost_usd = result.estimated_cost_usd
        run.latency_ms = result.latency_ms
        run.completed_at = datetime.now(UTC)

    @staticmethod
    def _complete_failure(run: AIRun, exc: APIException) -> None:
        run.status = "failed"
        run.error_code = exc.code
        run.error_message = exc.message[:1000]
        run.completed_at = datetime.now(UTC)

    async def execute(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        feature: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
        entity_type: str | None = None,
        entity_id: str | None = None,
        prompt_version: str = "v1",
        web_search: bool = False,
    ) -> tuple[BaseModel, AIRun]:
        run = await self._prepare_run(
            db,
            current_user=current_user,
            feature=feature,
            entity_type=entity_type,
            entity_id=entity_id,
            prompt_version=prompt_version,
            model_overrides=(
                {
                    "openai": settings.AI_WEB_SEARCH_MODEL,
                    **(
                        {"gemini": settings.AI_GEMINI_WEB_SEARCH_MODEL}
                        if settings.AI_GEMINI_WEB_SEARCH_MODEL
                        else {}
                    ),
                }
                if web_search
                else None
            ),
        )
        try:
            result = await self.provider_gateway.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                provider=run.provider,
                model=run.model_name,
                web_search=web_search,
            )
        except APIException as exc:
            self._complete_failure(run, exc)
            await db.commit()
            raise
        self._complete_success(run, result)
        await db.commit()
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
        run = await self._prepare_run(
            db,
            current_user=current_user,
            feature="speech_to_text",
            entity_type=None,
            entity_id=None,
            prompt_version="audio-v1",
            model_overrides={
                "openai": settings.AI_TRANSCRIPTION_MODEL,
                **(
                    {"gemini": settings.AI_GEMINI_TRANSCRIPTION_MODEL}
                    if settings.AI_GEMINI_TRANSCRIPTION_MODEL
                    else {}
                ),
            },
        )
        try:
            result = await self.provider_gateway.transcribe_audio(
                file_name=file_name,
                content=content,
                content_type=content_type,
                provider=run.provider,
                model=run.model_name,
            )
        except APIException as exc:
            self._complete_failure(run, exc)
            await db.commit()
            raise
        self._complete_success(run, result)
        await db.commit()
        return TranscriptionResponse.model_validate(result.output), run

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
