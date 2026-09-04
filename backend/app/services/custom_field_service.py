from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.repositories.setting_repository import SettingRepository
from app.schemas.crm_schemas import CustomFieldDefinition, CustomFieldValue

CUSTOM_FIELD_ENTITY_TYPES = ("Lead", "Contact", "Company", "Deal")


def normalize_custom_field_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    canonical = {value.lower(): value for value in CUSTOM_FIELD_ENTITY_TYPES}.get(normalized)
    if canonical is None:
        raise APIException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_CUSTOM_FIELD_ENTITY",
            message=f"Unsupported custom field entity '{entity_type}'",
        )
    return canonical


class CustomFieldService:
    """Shared custom-field definition lookup and value validation."""

    def __init__(self, repository: SettingRepository | None = None) -> None:
        self.repository = repository or SettingRepository()

    async def list_definitions(
        self, db: AsyncSession, *, organization_id: str, entity_type: str
    ) -> list[CustomFieldDefinition]:
        canonical_entity = normalize_custom_field_entity_type(entity_type)
        fields = await self.repository.list_custom_fields(
            db, organization_id=organization_id, entity_type=canonical_entity
        )
        return [
            CustomFieldDefinition(
                field_name=field.field_name,
                field_type=field.field_type,
                label=field.label,
                options=field.options or [],
            )
            for field in fields
        ]

    async def validate_values(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        entity_type: str,
        values: dict[str, CustomFieldValue],
    ) -> dict[str, CustomFieldValue]:
        if not values:
            return {}

        canonical_entity = normalize_custom_field_entity_type(entity_type)
        definitions = await self.repository.list_custom_fields(
            db, organization_id=organization_id, entity_type=canonical_entity
        )
        fields_by_name = {field.field_name: field for field in definitions}
        unknown_fields = sorted(set(values) - set(fields_by_name))
        if unknown_fields:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="INVALID_CUSTOM_FIELDS",
                message=(
                    f"Unknown {canonical_entity.lower()} custom field(s): "
                    f"{', '.join(unknown_fields)}"
                ),
            )

        for field_name, value in values.items():
            if value is None:
                continue
            definition = fields_by_name[field_name]
            field_type = definition.field_type.lower()
            is_valid = (
                (field_type == "text" and isinstance(value, str))
                or (
                    field_type == "number"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                )
                or (field_type == "boolean" and isinstance(value, bool))
                or (
                    field_type == "select"
                    and isinstance(value, str)
                    and value in (definition.options or [])
                )
            )
            if not is_valid:
                raise APIException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    code="INVALID_CUSTOM_FIELD_VALUE",
                    message=(
                        f"Invalid value for {canonical_entity.lower()} custom field "
                        f"'{field_name}'"
                    ),
                )
        return values


custom_field_service = CustomFieldService()
