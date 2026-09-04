from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.services.custom_field_service import CustomFieldService


def _field(
    name: str,
    field_type: str,
    *,
    label: str | None = None,
    options: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        field_name=name,
        field_type=field_type,
        label=label or name.replace("_", " ").title(),
        options=options or [],
    )


@pytest.mark.asyncio
async def test_list_definitions_is_tenant_and_entity_scoped():
    repository = AsyncMock()
    repository.list_custom_fields.return_value = [_field("region", "text")]
    service = CustomFieldService(repository)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_definitions(db, organization_id="org-1", entity_type="lead")

    assert result[0].field_name == "region"
    repository.list_custom_fields.assert_awaited_once_with(
        db, organization_id="org-1", entity_type="Lead"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("definition", "value"),
    [
        (_field("notes", "text"), "Call tomorrow"),
        (_field("employees", "number"), 25),
        (_field("qualified", "boolean"), True),
        (_field("tier", "select", options=["Gold", "Silver"]), "Gold"),
    ],
)
async def test_validate_values_accepts_supported_types(definition, value):
    repository = AsyncMock()
    repository.list_custom_fields.return_value = [definition]
    service = CustomFieldService(repository)
    db = AsyncMock(spec=AsyncSession)

    result = await service.validate_values(
        db,
        organization_id="org-1",
        entity_type="Company",
        values={definition.field_name: value},
    )

    assert result == {definition.field_name: value}


@pytest.mark.asyncio
async def test_validate_values_rejects_unknown_field_from_another_scope():
    repository = AsyncMock()
    repository.list_custom_fields.return_value = []
    service = CustomFieldService(repository)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.validate_values(
            db,
            organization_id="org-1",
            entity_type="Contact",
            values={"other_org_field": "secret"},
        )

    assert exc_info.value.code == "INVALID_CUSTOM_FIELDS"
    repository.list_custom_fields.assert_awaited_once_with(
        db, organization_id="org-1", entity_type="Contact"
    )


@pytest.mark.asyncio
async def test_validate_values_rejects_wrong_type():
    repository = AsyncMock()
    repository.list_custom_fields.return_value = [_field("employee_count", "number")]
    service = CustomFieldService(repository)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.validate_values(
            db,
            organization_id="org-1",
            entity_type="Company",
            values={"employee_count": True},
        )

    assert exc_info.value.code == "INVALID_CUSTOM_FIELD_VALUE"
