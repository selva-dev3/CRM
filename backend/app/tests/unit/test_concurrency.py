from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.concurrency import ensure_fresh_record
from app.core.errors import ConflictError


@pytest.mark.asyncio
async def test_matching_version_locks_record_and_allows_update():
    updated_at = datetime(2026, 9, 15, tzinfo=UTC)
    record = SimpleNamespace(updated_at=updated_at)
    db = SimpleNamespace(refresh=AsyncMock())

    await ensure_fresh_record(cast(AsyncSession, db), record, updated_at, "lead")

    db.refresh.assert_awaited_once_with(record, with_for_update=True)


@pytest.mark.asyncio
async def test_stale_version_returns_structured_conflict_without_mutating_record():
    expected = datetime(2026, 9, 14, tzinfo=UTC)
    actual = datetime(2026, 9, 15, tzinfo=UTC)
    record = SimpleNamespace(updated_at=actual)
    db = SimpleNamespace(refresh=AsyncMock())

    with pytest.raises(ConflictError) as exc_info:
        await ensure_fresh_record(cast(AsyncSession, db), record, expected, "deal")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "STALE_RECORD"
    assert exc_info.value.fields == {"expected_updated_at": actual.isoformat()}
