from app.core.errors import APIException
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.repositories.ai_repository import AIRepository

logger = get_logger(__name__)


class AIAuditService:
    """Persist metadata-only AI audit events independently of request rollbacks."""

    def __init__(self, repository: AIRepository | None = None) -> None:
        self.repository = repository or AIRepository()

    async def record_tool_execution(self, **metadata: object) -> None:
        try:
            async with AsyncSessionLocal() as db:
                await self.repository.create_tool_audit(db, **metadata)
                await db.commit()
        except Exception:
            logger.exception(
                "AI tool audit persistence failed request_id=%s tool=%s",
                metadata.get("request_id"),
                metadata.get("tool_name"),
            )
            raise APIException(
                status_code=503,
                code="AI_AUDIT_UNAVAILABLE",
                message="The AI tool audit could not be recorded.",
            ) from None


ai_audit_service = AIAuditService()
