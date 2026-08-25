"""Regression test: `except HTTPException` in get_zapier_config must not
raise NameError. The import was missing, so any HTTPException raised inside
the try-block crashed with NameError instead of propagating."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.integration_service import IntegrationService


@pytest.mark.asyncio
async def test_get_zapier_config_propagates_http_exception_without_name_error():
    service = IntegrationService(repository=AsyncMock())
    # Force an HTTPException from deep inside the try-block.
    service.repository.resolve_org_id = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="org inactive")
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_zapier_config(AsyncMock(spec=AsyncSession), current_user=None)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_zapier_config_wraps_non_http_errors():
    service = IntegrationService(repository=AsyncMock())
    service.repository.resolve_org_id = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(Exception) as exc_info:
        await service.get_zapier_config(AsyncMock(spec=AsyncSession), current_user=None)

    # Non-HTTP errors still map to the project's APIException 500 path.
    assert type(exc_info.value).__name__ == "APIException"
