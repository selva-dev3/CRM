from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError


async def ensure_fresh_record(
    db: AsyncSession,
    record,
    expected_updated_at: datetime | None,
    entity_name: str,
) -> None:
    """Lock and validate a record version before applying a user mutation."""
    if expected_updated_at is None:
        return
    await db.refresh(record, with_for_update=True)
    actual = getattr(record, "updated_at", None)
    if actual != expected_updated_at:
        raise ConflictError(
            code="STALE_RECORD",
            message=f"This {entity_name} changed since it was loaded. Review the latest values and try again.",
            fields={"expected_updated_at": actual.isoformat() if actual else None},
        )
