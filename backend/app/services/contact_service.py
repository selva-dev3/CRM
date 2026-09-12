from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.contact import Contact
from app.repositories.call_repository import CallRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.email_repository import EmailRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.whatsapp_repository import WhatsAppRepository
from app.schemas.crm_schemas import (
    ContactActivityResponse,
    ContactAddressResponse,
    ContactAddressUpdate,
    ContactCreate,
    ContactEmailResponse,
    ContactUpdate,
    CustomFieldDefinition,
)
from app.services.auth_service import api_key_scope_allows, auth_service
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

    @staticmethod
    def _identity(email: str | None, phone: str | None) -> tuple[str, str | None]:
        normalized_email = (email or "").strip().casefold()
        normalized_phone = "".join(char for char in (phone or "") if char.isdigit()) or None
        return normalized_email, normalized_phone

    def __init__(
        self,
        repository: ContactRepository | None = None,
        custom_field_service_instance: CustomFieldService | None = None,
        whatsapp_repository: WhatsAppRepository | None = None,
    ) -> None:
        self.repository = repository or ContactRepository()
        self.deal_repository = DealRepository()
        self.call_repository = CallRepository()
        self.email_repository = EmailRepository()
        self.note_repository = NoteRepository()
        self.custom_field_service = custom_field_service_instance or custom_field_service
        self.whatsapp_repository = whatsapp_repository or WhatsAppRepository()

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
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "contacts")
        contacts = await self.repository.list_by_org(
            db,
            organization_id=org_id,
            page=page,
            limit=limit,
            search=search,
            access=access,
        )
        return [contact_to_dict(c) for c in contacts]

    async def count_contacts(
        self,
        db: AsyncSession,
        *,
        search: str | None,
        current_user: User,
    ) -> int:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "contacts")
        return await self.repository.count_by_org(
            db, organization_id=organization_id, search=search, access=access
        )

    async def get_starred_contacts(
        self, db: AsyncSession, *, organization_id: str, current_user: User
    ) -> list[dict]:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "contacts")
        contacts = await self.repository.list_starred(
            db, organization_id=organization_id, access=access
        )
        return [contact_to_dict(c) for c in contacts]

    async def list_custom_fields(
        self, db: AsyncSession, current_user: User
    ) -> list[CustomFieldDefinition]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.custom_field_service.list_definitions(
            db, organization_id=organization_id, entity_type="Contact"
        )

    async def require_contact(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        populate_existing: bool = False,
        current_user: User | None = None,
    ) -> Contact:
        access = None
        if current_user:
            from app.services.record_access_service import record_access_service

            access = await record_access_service.resolve(db, current_user, "contacts")
        contact = await self.repository.get_by_id_scoped(
            db,
            contact_id=contact_id,
            organization_id=organization_id,
            populate_existing=populate_existing,
            access=access,
        )
        if not contact:
            raise NotFoundError(message=f"Contact '{contact_id}' not found")
        return contact

    async def get_contact(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        contact = await self.require_contact(
            db, contact_id, organization_id=organization_id, current_user=current_user
        )
        return contact_to_dict(contact)

    async def get_billing_address(
        self, db: AsyncSession, contact_id: str, *, organization_id: str
    ) -> ContactAddressResponse:
        await self.require_contact(db, contact_id, organization_id=organization_id)
        address = await self.repository.get_address(
            db, contact_id=contact_id, organization_id=organization_id
        )
        if not address:
            return ContactAddressResponse()
        return ContactAddressResponse.model_validate(address, from_attributes=True)

    async def update_billing_address(
        self,
        db: AsyncSession,
        contact_id: str,
        payload: ContactAddressUpdate,
        *,
        organization_id: str,
    ) -> ContactAddressResponse:
        await self.require_contact(db, contact_id, organization_id=organization_id)
        address = await self.repository.get_address(
            db, contact_id=contact_id, organization_id=organization_id
        )
        data = payload.model_dump()
        if address:
            for field, value in data.items():
                setattr(address, field, value)
        else:
            address = await self.repository.create_address(db, contact_id=contact_id, data=data)
        await self._commit(db, "Failed to save contact billing address")
        await db.refresh(address)
        return ContactAddressResponse.model_validate(address, from_attributes=True)

    async def list_contact_activities(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        current_user: User,
        page: int = 1,
        limit: int = 15,
    ) -> list[ContactActivityResponse]:
        contact = await self.require_contact(db, contact_id, organization_id=organization_id)
        source_limit = page * limit
        notes = await self.note_repository.list_by_entity(
            db,
            entity_type="contact",
            entity_id=contact.id,
            organization_id=organization_id,
            page=1,
            limit=source_limit,
        )
        permissions = await auth_service.get_user_permissions(db, current_user)
        can_read_calls = "calls:read" in permissions and api_key_scope_allows(
            current_user, "calls:read"
        )
        calls = (
            await self.call_repository.list_by_contact(
                db,
                contact_id=contact.id,
                organization_id=organization_id,
                page=1,
                limit=source_limit,
            )
            if can_read_calls
            else []
        )
        deal_activities = await self.deal_repository.list_activities_by_contact(
            db,
            contact_id=contact.id,
            organization_id=organization_id,
            limit=source_limit,
        )
        activities = [
            ContactActivityResponse(
                id=note.id,
                type="Note",
                description=note.content,
                created_at=str(note.created_at),
            )
            for note in notes
        ]
        activities.extend(
            ContactActivityResponse(
                id=call.id,
                type=call.call_type or "Call",
                description=call.notes or "Call logged",
                created_at=str(call.timestamp),
            )
            for call in calls
        )
        activities.extend(
            ContactActivityResponse(
                id=activity.id,
                type="Deal Activity",
                description=activity.action,
                created_at=str(activity.timestamp),
            )
            for activity in deal_activities
        )
        whatsapp_permissions = {
            p
            for p in permissions
            if p.startswith("whatsapp:") and api_key_scope_allows(current_user, p)
        }
        if {"whatsapp:read_assigned", "whatsapp:read_all"} & whatsapp_permissions:
            from app.repositories.whatsapp_repository import WhatsAppRepository

            for message in await WhatsAppRepository().timeline_messages(
                db, current_user, whatsapp_permissions, contact_id=contact.id, limit=source_limit
            ):
                activities.append(
                    ContactActivityResponse(
                        id=f"whatsapp-{message.id}",
                        type="WhatsApp",
                        description=f"{message.direction} · {message.message_type} · {message.source} · {message.status}",
                        created_at=str(message.provider_timestamp or message.created_at),
                    )
                )
        activities.sort(key=lambda activity: activity.created_at, reverse=True)
        offset = (page - 1) * limit
        return activities[offset : offset + limit]

    async def count_contact_activities(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        current_user: User,
    ) -> int:
        contact = await self.require_contact(db, contact_id, organization_id=organization_id)
        permissions = await auth_service.get_user_permissions(db, current_user)
        total = await self.note_repository.count_by_entity(
            db,
            entity_type="contact",
            entity_id=contact.id,
            organization_id=organization_id,
        )
        if "calls:read" in permissions and api_key_scope_allows(current_user, "calls:read"):
            total += await self.call_repository.count_by_contact(
                db, contact_id=contact.id, organization_id=organization_id
            )
        total += await self.deal_repository.count_activities_by_contact(
            db, contact_id=contact.id, organization_id=organization_id
        )
        whatsapp_permissions = {
            permission
            for permission in permissions
            if permission.startswith("whatsapp:") and api_key_scope_allows(current_user, permission)
        }
        if {"whatsapp:read_assigned", "whatsapp:read_all"} & whatsapp_permissions:
            total += await self.whatsapp_repository.count_timeline_messages(
                db,
                current_user,
                whatsapp_permissions,
                contact_id=contact.id,
            )
        return total

    async def list_contact_emails(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 15,
    ) -> list[ContactEmailResponse]:
        if page > 1 and limit is None:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="limit is required when page is greater than 1",
            )
        contact = await self.require_contact(db, contact_id, organization_id=organization_id)
        emails = await self.email_repository.list_for_contact(
            db,
            organization_id=organization_id,
            contact_id=contact.id,
            recipient_email=contact.email,
            limit=limit,
            offset=(page - 1) * limit,
        )
        return [
            ContactEmailResponse(
                id=email.id,
                from_email=email.from_email,
                to=[email.to_email],
                subject=email.subject,
                body=email.body_text,
                sent_at=str(email.sent_at),
            )
            for email in emails
        ]

    async def count_contact_emails(
        self, db: AsyncSession, contact_id: str, *, organization_id: str
    ) -> int:
        contact = await self.require_contact(db, contact_id, organization_id=organization_id)
        return await self.email_repository.count_for_contact(
            db,
            organization_id=organization_id,
            contact_id=contact.id,
            recipient_email=contact.email,
        )

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
        normalized_email, normalized_phone = self._identity(payload.email, payload.phone)
        if not normalized_email:
            raise APIException(message="Contact email is required", status_code=422)
        if settings.WHATSAPP_ENABLED:
            # Contact inserts fire the phone-normalization trigger. Take its
            # advisory guard before the tenant row lock used for deduplication.
            await self.whatsapp_repository.lock_phone_guard(db, org_id)
        await self.repository.lock_organization(db, org_id)
        duplicate = await self.repository.find_duplicate(
            db,
            organization_id=org_id,
            email=normalized_email,
            phone=normalized_phone,
        )
        if duplicate:
            raise APIException(
                message="A matching contact already exists in this organization",
                code="CONTACT_DUPLICATE",
                status_code=409,
            )
        if payload.company_id and not await self.repository.company_exists(
            db, company_id=payload.company_id, organization_id=org_id
        ):
            raise NotFoundError(message="Company not found")
        custom_fields = await self.custom_field_service.validate_values(
            db,
            organization_id=org_id,
            entity_type="Contact",
            values=payload.custom_fields or {},
        )
        data = {
            "organization_id": org_id,
            "name": full_name,
            "email": normalized_email,
            "phone": getattr(payload, "phone", None),
            "position": position,
            "company_id": getattr(payload, "company_id", None),
            "owner_id": current_user.id,
            "created_by": current_user.id,
            "custom_fields": custom_fields,
        }
        contact = await self.repository.create(db, data=data)
        await self.whatsapp_repository.prepare_crm_phone(db, org_id, contact)
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
        self,
        db: AsyncSession,
        contact_id: str,
        payload: ContactUpdate,
        *,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        phone_change_requested = payload.phone is not None
        if settings.WHATSAPP_ENABLED and phone_change_requested:
            # Acquire before the Contact read so verification decisions use a
            # fresh state serialized with every other phone-identity writer.
            await self.whatsapp_repository.lock_phone_guard(db, organization_id)
        contact = await self.require_contact(
            db,
            contact_id,
            organization_id=organization_id,
            populate_existing=phone_change_requested,
            current_user=current_user,
        )

        candidate_email = payload.email if payload.email is not None else contact.email
        candidate_phone = payload.phone if payload.phone is not None else contact.phone
        normalized_email, normalized_phone = self._identity(candidate_email, candidate_phone)
        await self.repository.lock_organization(db, organization_id)
        duplicate = await self.repository.find_duplicate(
            db,
            organization_id=organization_id,
            email=normalized_email,
            phone=normalized_phone,
            exclude_id=contact.id,
        )
        if duplicate:
            raise APIException(
                message="A matching contact already exists in this organization",
                code="CONTACT_DUPLICATE",
                status_code=409,
            )

        raw_name = getattr(payload, "name", None)
        first_name = getattr(payload, "first_name", None)
        last_name = getattr(payload, "last_name", None)
        if raw_name:
            contact.name = raw_name.strip()
        elif first_name or last_name:
            contact.name = f"{first_name or ''} {last_name or ''}".strip()

        if payload.email:
            contact.email = normalized_email
        if payload.phone is not None:
            contact.phone = payload.phone
            await self.whatsapp_repository.prepare_crm_phone(db, organization_id, contact)
        if payload.company_id is not None:
            if payload.company_id and not await self.repository.company_exists(
                db,
                company_id=payload.company_id,
                organization_id=organization_id,
            ):
                raise NotFoundError(message="Company not found")
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

    async def delete_contact(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        contact = await self.require_contact(
            db, contact_id, organization_id=organization_id, current_user=current_user
        )
        await self.whatsapp_repository.detach_crm_identities(
            db, organization_id, contact_ids={contact.id}
        )
        await self.repository.delete(db, contact)
        await self._commit(db, "Failed to delete contact")
        return {"message": f"Contact {contact_id} deleted successfully", "status": "success"}

    async def merge_contacts(
        self,
        db: AsyncSession,
        primary_id: str,
        secondary_id: str,
        *,
        organization_id: str,
    ) -> dict:
        primary = await self.repository.get_by_id_scoped(
            db, contact_id=primary_id, organization_id=organization_id
        )
        secondary = await self.repository.get_by_id_scoped(
            db, contact_id=secondary_id, organization_id=organization_id
        )
        if not primary or not secondary:
            raise NotFoundError(message="One or both contacts not found")
        raise APIException(
            message="Contact merging is not implemented",
            code="CONTACT_MERGE_UNAVAILABLE",
            status_code=501,
        )

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: list[str],
        *,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        access = None
        if current_user:
            from app.services.record_access_service import record_access_service

            access = await record_access_service.resolve(db, current_user, "contacts")
        contacts = await self.repository.list_by_ids(
            db, ids, organization_id=organization_id, access=access
        )
        await self.whatsapp_repository.detach_crm_identities(
            db, organization_id, contact_ids={contact.id for contact in contacts}
        )
        for contact in contacts:
            await self.repository.delete(db, contact)
        await self._commit(db, "Failed to bulk delete contacts")
        return {"affected_count": len(contacts), "message": "Contacts deleted successfully"}

    async def set_starred(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        starred: bool,
        organization_id: str,
    ) -> dict:
        contact = await self.require_contact(db, contact_id, organization_id=organization_id)
        contact.is_starred = starred
        await self._commit(db, "Failed to update contact")
        return {
            "message": f"Contact {contact_id} {'starred' if starred else 'unstarred'}",
            "status": "success",
        }

    async def list_company_contacts(
        self,
        db: AsyncSession,
        company_id: str,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 15,
        current_user: User | None = None,
    ) -> list[dict]:
        from app.services.record_access_service import record_access_service

        access = (
            await record_access_service.resolve(db, current_user, "contacts")
            if current_user
            else None
        )
        contacts = await self.repository.list_by_company(
            db,
            company_id,
            organization_id=organization_id,
            page=page,
            limit=limit,
            **({"access": access} if access is not None else {}),
        )
        return [contact_to_dict(c) for c in contacts]

    async def count_company_contacts(
        self, db: AsyncSession, company_id: str, *, organization_id: str,
        current_user: User | None = None,
    ) -> int:
        from app.services.record_access_service import record_access_service

        access = (
            await record_access_service.resolve(db, current_user, "contacts")
            if current_user
            else None
        )
        return await self.repository.count_by_company(
            db, company_id, organization_id=organization_id,
            **({"access": access} if access is not None else {}),
        )

    async def list_contact_deals(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 15,
        current_user: User | None = None,
    ) -> list[dict]:
        await self.require_contact(
            db, contact_id, organization_id=organization_id, current_user=current_user
        )
        from app.services.deal_service import deal_to_dict
        from app.services.record_access_service import record_access_service

        access = (
            await record_access_service.resolve(db, current_user, "deals")
            if current_user
            else None
        )
        deals = await self.deal_repository.list_by_contact(
            db,
            contact_id=contact_id,
            organization_id=organization_id,
            page=page,
            limit=limit,
            **({"access": access} if access is not None else {}),
        )
        return [deal_to_dict(deal) for deal in deals]

    async def count_contact_deals(
        self, db: AsyncSession, contact_id: str, *, organization_id: str,
        current_user: User | None = None,
    ) -> int:
        await self.require_contact(
            db, contact_id, organization_id=organization_id, current_user=current_user
        )
        from app.services.record_access_service import record_access_service

        access = (
            await record_access_service.resolve(db, current_user, "deals")
            if current_user
            else None
        )
        return await self.deal_repository.count_by_contact(
            db, contact_id=contact_id, organization_id=organization_id,
            **({"access": access} if access is not None else {}),
        )

    async def list_contact_calls(
        self,
        db: AsyncSession,
        contact_id: str,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 15,
    ) -> list[dict]:
        await self.require_contact(db, contact_id, organization_id=organization_id)
        from app.services.call_service import call_to_dict

        calls = await self.call_repository.list_by_contact(
            db,
            contact_id=contact_id,
            organization_id=organization_id,
            page=page,
            limit=limit,
        )
        return [call_to_dict(call) for call in calls]

    async def count_contact_calls(
        self, db: AsyncSession, contact_id: str, *, organization_id: str
    ) -> int:
        await self.require_contact(db, contact_id, organization_id=organization_id)
        return await self.call_repository.count_by_contact(
            db, contact_id=contact_id, organization_id=organization_id
        )


contact_service = ContactService()
