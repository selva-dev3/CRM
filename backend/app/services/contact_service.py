from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import ContactCreate, ContactUpdate, CustomFieldDefinition
from app.services.custom_field_service import CustomFieldService, custom_field_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def contact_to_dict(contact: Contact) -> dict:
    parts = contact.name.split() if contact.name else []
    is_starred = bool(getattr(contact, "is_starred", False))
    return {
        "id": contact.id,
        "name": contact.name or "",
        "first_name": parts[0] if parts else "",
        "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
        "email": contact.email or "",
        "phone": contact.phone,
        "position": contact.position,
        "company_id": contact.company_id,
        "is_starred": is_starred,
        "status": "Star Contact" if is_starred else None,
        "created_at": str(contact.created_at) if contact.created_at else None,
        "custom_fields": contact.custom_fields or {},
    }


class ContactService:
    """Business logic for the Contact domain."""

    def __init__(
        self,
        repository: ContactRepository | None = None,
        custom_field_service_instance: CustomFieldService | None = None,
    ) -> None:
        self.repository = repository or ContactRepository()
        self.custom_field_service = custom_field_service_instance or custom_field_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_contacts(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        contacts = await self.repository.list_by_org(
            db, organization_id=org_id, page=page, limit=limit, search=search
        )
        return [contact_to_dict(c) for c in contacts]

    async def get_starred_contacts(self, db: AsyncSession) -> list[dict]:
        contacts = await self.repository.list_starred(db)
        return [contact_to_dict(c) for c in contacts]

    async def list_custom_fields(
        self, db: AsyncSession, current_user: User
    ) -> list[CustomFieldDefinition]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.custom_field_service.list_definitions(
            db, organization_id=organization_id, entity_type="Contact"
        )

    async def get_contact(self, db: AsyncSession, contact_id: str) -> dict:
        contact = await self.repository.get_by_id(db, contact_id)
        if not contact:
            raise NotFoundError(message=f"Contact '{contact_id}' not found")
        return contact_to_dict(contact)

    async def _build_name_parts(
        self,
        raw_name: str | None,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
    ) -> tuple[str, str, str]:
        full_name = (raw_name or "").strip()
        if not full_name and (first_name or last_name):
            full_name = f"{first_name or ''} {last_name or ''}".strip()
        if not full_name:
            full_name = (email or "").split("@")[0]
        parts = full_name.split()
        first = first_name or (parts[0] if parts else "")
        last = last_name or (" ".join(parts[1:]) if len(parts) > 1 else "Contact")
        return full_name, first, last

    async def create_contact(
        self, db: AsyncSession, payload: ContactCreate, current_user: User
    ) -> dict:
        raw_name = getattr(payload, "name", None) or ""
        first_name = getattr(payload, "first_name", None) or ""
        last_name = getattr(payload, "last_name", None) or ""
        full_name, _, _ = await self._build_name_parts(
            raw_name, first_name, last_name, payload.email
        )
        position = (
            getattr(payload, "position", None)
            or getattr(payload, "job_title", None)
            or "Representative"
        )
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        custom_fields = await self.custom_field_service.validate_values(
            db,
            organization_id=org_id,
            entity_type="Contact",
            values=payload.custom_fields or {},
        )
        data = {
            "organization_id": org_id,
            "name": full_name,
            "email": payload.email,
            "phone": getattr(payload, "phone", None),
            "position": position,
            "company_id": getattr(payload, "company_id", None),
            "custom_fields": custom_fields,
        }
        contact = await self.repository.create(db, data=data)
        await self._commit(db, "Failed to create contact")
        await db.refresh(contact)
        await notification_service.notify(
            db,
            event_name="contact.created",
            organization_id=contact.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="contact",
            entity_id=contact.id,
            data={
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "phone": contact.phone,
                "position": contact.position,
                "company_id": contact.company_id,
            },
        )
        return contact_to_dict(contact)

    async def update_contact(
        self, db: AsyncSession, contact_id: str, payload: ContactUpdate
    ) -> dict:
        contact = await self.repository.get_by_id(db, contact_id)
        if not contact:
            raise NotFoundError(message=f"Contact '{contact_id}' not found")

        raw_name = getattr(payload, "name", None)
        first_name = getattr(payload, "first_name", None)
        last_name = getattr(payload, "last_name", None)
        if raw_name:
            contact.name = raw_name.strip()
        elif first_name or last_name:
            contact.name = f"{first_name or ''} {last_name or ''}".strip()

        if payload.email:
            contact.email = payload.email
        if payload.phone is not None:
            contact.phone = payload.phone
        if payload.company_id is not None:
            contact.company_id = payload.company_id

        position = getattr(payload, "position", None) or getattr(payload, "job_title", None)
        if position is not None:
            contact.position = position

        if payload.custom_fields is not None:
            contact.custom_fields = await self.custom_field_service.validate_values(
                db,
                organization_id=contact.organization_id,
                entity_type="Contact",
                values=payload.custom_fields,
            )

        await self._commit(db, "Failed to update contact")
        await db.refresh(contact)
        await notification_service.notify(
            db,
            event_name="contact.updated",
            organization_id=contact.organization_id,
            entity_type="contact",
            entity_id=contact.id,
            data={
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "company_id": contact.company_id,
            },
        )
        return contact_to_dict(contact)

    async def delete_contact(self, db: AsyncSession, contact_id: str) -> dict:
        contact = await self.repository.get_by_id(db, contact_id)
        if not contact:
            raise NotFoundError(message=f"Contact '{contact_id}' not found")
        await self.repository.delete(db, contact)
        await self._commit(db, "Failed to delete contact")
        return {"message": f"Contact {contact_id} deleted successfully", "status": "success"}

    async def merge_contacts(self, db: AsyncSession, primary_id: str, secondary_id: str) -> dict:
        primary = await self.repository.get_by_id(db, primary_id)
        secondary = await self.repository.get_by_id(db, secondary_id)
        if not primary or not secondary:
            raise NotFoundError(message="One or both contacts not found")
        return {
            "message": f"Merged contact {secondary_id} into {primary_id}",
            "status": "success",
        }

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        contacts = await self.repository.list_by_ids(db, ids)
        for contact in contacts:
            await self.repository.delete(db, contact)
        await self._commit(db, "Failed to bulk delete contacts")
        return {"affected_count": len(contacts), "message": "Contacts deleted successfully"}

    async def set_starred(self, db: AsyncSession, contact_id: str, *, starred: bool) -> dict:
        contact = await self.repository.get_by_id(db, contact_id)
        if not contact:
            raise NotFoundError(message=f"Contact '{contact_id}' not found")
        contact.is_starred = starred
        await self._commit(db, "Failed to update contact")
        return {
            "message": f"Contact {contact_id} {'starred' if starred else 'unstarred'}",
            "status": "success",
        }

    async def list_company_contacts(self, db: AsyncSession, company_id: str) -> list[dict]:
        contacts = await self.repository.list_by_company(db, company_id)
        return [contact_to_dict(c) for c in contacts]


contact_service = ContactService()
