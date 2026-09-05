import asyncio
import io
import uuid
from datetime import UTC, datetime

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Lead, User
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import (
    CallLogBase,
    CustomFieldDefinition,
    EmailSendRequest,
    LeadConvertRequest,
    LeadCreate,
    LeadUpdate,
    TaskCreate,
)
from app.services.custom_field_service import CustomFieldService, custom_field_service
from app.services.document_service import (
    _normalize_mime_type,
    _read_upload_with_limit,
    _sanitize_filename,
    _split_extension,
    _validate_upload,
)
from app.services.notification_service import notification_service
from app.services.org_service import organization_service
from app.services.s3_service import s3_service

LEAD_SOURCES = ["Website", "LinkedIn", "Referral", "Cold Call", "Event", "Partner"]
LEAD_STATUSES = ["New", "Contacted", "Qualified", "Unqualified", "Converted"]


def _read_s3_object(key: str) -> bytes:
    s3_obj = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=key)
    return s3_obj["Body"].read()


def lead_to_dict(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "title": lead.title,
        "company": lead.company,
        "contact_name": lead.contact_name,
        "email": lead.email,
        "phone": getattr(lead, "phone", None),
        "website": getattr(lead, "website", None),
        "industry": getattr(lead, "industry", None),
        "company_size": getattr(lead, "company_size", None),
        "country": getattr(lead, "country", None),
        "state": getattr(lead, "state", None),
        "city": getattr(lead, "city", None),
        "address": getattr(lead, "address", None),
        "postal_code": getattr(lead, "postal_code", None),
        "status": lead.status,
        "source": lead.source,
        "score": getattr(lead, "score", 50.0),
        "assigned_to": getattr(lead, "assigned_to", None),
        "is_archived": getattr(lead, "is_archived", False),
        "custom_fields": getattr(lead, "custom_fields", None) or {},
        "organization_id": lead.organization_id,
        "created_at": str(lead.created_at) if lead.created_at else "",
    }


class LeadService:
    def __init__(
        self,
        repository: LeadRepository | None = None,
        custom_field_service_instance: CustomFieldService | None = None,
    ) -> None:
        self.repository = repository or LeadRepository()
        self.custom_field_service = custom_field_service_instance or custom_field_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_leads(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        lead_status: str | None = None,
    ) -> list[dict]:
        leads = await self.repository.list_leads(
            db,
            page=page,
            limit=limit,
            organization_id=organization_id,
            search=search,
            status=lead_status,
        )
        return [lead_to_dict(lead) for lead in leads]

    async def count_leads(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        lead_status: str | None = None,
    ) -> int:
        return await self.repository.count_leads(
            db,
            organization_id=organization_id,
            search=search,
            status=lead_status,
        )

    async def list_custom_fields(
        self, db: AsyncSession, current_user: User
    ) -> list[CustomFieldDefinition]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.custom_field_service.list_definitions(
            db, organization_id=organization_id, entity_type="Lead"
        )

    async def require_lead(self, db: AsyncSession, lead_id: str, *, organization_id: str) -> Lead:
        lead = await self.repository.get_by_id_for_org(db, lead_id, organization_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        return lead

    async def get_lead(self, db: AsyncSession, lead_id: str, *, organization_id: str) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        return lead_to_dict(lead)

    async def _resolve_organization_id(
        self, db: AsyncSession, org_id: str | None, current_user: User | None = None
    ) -> str | None:
        user_org = current_user.organization_id if current_user else None
        if not user_org:
            return None
        if org_id and org_id != user_org:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Organization does not match the current user's organization.",
            )
        organization = await self.repository.get_organization(db, user_org)
        return organization.id if organization else None

    async def _resolve_assigned_to(
        self, db: AsyncSession, assigned_to: str | None, organization_id: str | None
    ) -> str | None:
        if not assigned_to:
            return None
        user = await self.repository.get_user(db, assigned_to)
        if not user or not organization_id or user.organization_id != organization_id:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Assignee must be an existing user in the lead's organization.",
            )
        return assigned_to

    async def create_lead(
        self, db: AsyncSession, payload: LeadCreate, current_user: User | None = None
    ) -> dict:
        org_id = await self._resolve_organization_id(db, payload.organization_id, current_user)
        if not org_id:
            raise ForbiddenError(message="Organization context is required.")
        assigned_to = await self._resolve_assigned_to(db, payload.assigned_to, org_id)
        custom_fields = await self.custom_field_service.validate_values(
            db,
            organization_id=org_id,
            entity_type="Lead",
            values=payload.custom_fields,
        )
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "company": payload.company,
            "contact_name": payload.contact_name,
            "email": payload.email,
            "phone": payload.phone,
            "website": payload.website,
            "industry": payload.industry,
            "company_size": payload.company_size,
            "country": payload.country,
            "state": payload.state,
            "city": payload.city,
            "address": payload.address,
            "postal_code": payload.postal_code,
            "status": payload.status,
            "source": payload.source,
            "score": payload.score if payload.score is not None else 50.0,
            "assigned_to": assigned_to,
            "is_archived": payload.is_archived if payload.is_archived is not None else False,
            "custom_fields": custom_fields,
        }
        lead = await self.repository.create(db, data=data)
        await self._commit(db, "Failed to create lead")
        await db.refresh(lead)
        await notification_service.notify(
            db,
            event_name="lead.created",
            organization_id=lead.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="lead",
            entity_id=lead.id,
            assigned_to=lead.assigned_to,
            data={
                "id": lead.id,
                "title": lead.title,
                "company": lead.company,
                "contact_name": lead.contact_name,
                "email": lead.email,
                "status": lead.status,
                "source": lead.source,
                "owner": lead.assigned_to,
            },
        )
        return lead_to_dict(lead)

    async def update_lead(
        self, db: AsyncSession, lead_id: str, payload: LeadUpdate, current_user: User
    ) -> dict:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            raise ForbiddenError(message="Organization context is required.")

        lead = await self.repository.get_by_id_for_org(db, lead_id, organization_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")

        updates = payload.model_dump(exclude_unset=True)
        requested_org = updates.pop("organization_id", organization_id)
        if requested_org != organization_id:
            raise ForbiddenError(message="A lead cannot be moved to another organization.")
        if "assigned_to" in updates:
            updates["assigned_to"] = await self._resolve_assigned_to(
                db, updates["assigned_to"], organization_id
            )
        if "custom_fields" in updates:
            updates["custom_fields"] = await self.custom_field_service.validate_values(
                db,
                organization_id=organization_id,
                entity_type="Lead",
                values=updates["custom_fields"] or {},
            )

        becoming_qualified = updates.get("status") == "Qualified" and lead.status != "Qualified"
        if becoming_qualified and (
            not lead.company.strip() or not lead.contact_name.strip() or not lead.email.strip()
        ):
            raise APIException(
                status_code=422,
                message="Company, contact name and email are required to qualify a lead",
            )

        for field, value in updates.items():
            setattr(lead, field, value)
        if becoming_qualified:
            await self.repository.record_qualification(db, lead, actor_id=current_user.id)
        await self._commit(db, "Failed to update lead")
        await notification_service.notify(
            db,
            event_name="lead.updated",
            organization_id=lead.organization_id,
            entity_type="lead",
            entity_id=lead.id,
            assigned_to=lead.assigned_to,
            data={
                "id": lead.id,
                "title": lead.title,
                "company": lead.company,
                "status": lead.status,
            },
        )
        return lead_to_dict(lead)

    async def delete_lead(self, db: AsyncSession, lead_id: str, *, organization_id: str) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        await self.repository.delete(db, lead)
        await self._commit(db, "Failed to delete lead")
        return {"message": f"Lead {lead_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str], *, organization_id: str) -> dict:
        if not ids:
            return {"affected_count": 0, "message": "No lead IDs provided"}
        leads = await self.repository.list_by_ids(db, ids, organization_id=organization_id)
        for lead in leads:
            await self.repository.delete(db, lead)
        await self._commit(db, "Bulk delete failed")
        return {
            "affected_count": len(leads),
            "message": f"Successfully deleted {len(leads)} lead(s)",
        }

    async def bulk_archive(self, db: AsyncSession, ids: list[str], *, organization_id: str) -> dict:
        if not ids:
            return {"affected_count": 0, "message": "No lead IDs provided"}
        leads = await self.repository.list_by_ids(db, ids, organization_id=organization_id)
        for lead in leads:
            lead.is_archived = True
        await self._commit(db, "Bulk archive failed")
        return {
            "affected_count": len(leads),
            "message": f"Successfully archived {len(leads)} lead(s)",
        }

    async def bulk_update_status(
        self,
        db: AsyncSession,
        ids: list[str],
        status_value: str,
        *,
        organization_id: str,
    ) -> dict:
        if not ids:
            return {"affected_count": 0, "message": "No lead IDs provided"}

        normalized_statuses = {lead_status.lower(): lead_status for lead_status in LEAD_STATUSES}
        canonical_status = normalized_statuses.get(status_value.strip().lower())
        if not canonical_status:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Unsupported lead status '{status_value}'.",
            )

        leads = await self.repository.list_by_ids(db, ids, organization_id=organization_id)
        for lead in leads:
            lead.status = canonical_status
        await self._commit(db, "Bulk status update failed")
        return {
            "affected_count": len(leads),
            "message": f"Status updated to {canonical_status}",
        }

    async def check_duplicate(self, db: AsyncSession, email: str, *, organization_id: str) -> dict:
        duplicate = await self.repository.get_by_email(db, email, organization_id=organization_id)
        return {
            "is_duplicate": bool(duplicate),
            "matched_lead_id": duplicate.id if duplicate else None,
        }

    async def convert_lead(
        self, db: AsyncSession, lead_id: str, payload: LeadConvertRequest, current_user: User
    ) -> dict:
        organization_id = current_user.organization_id
        if not organization_id:
            raise ForbiddenError(message="Organization membership is required")
        try:
            lead = await self.repository.lock_conversion(db, lead_id, organization_id)
            if not lead:
                raise NotFoundError(message="Lead not found")
            if lead.status == "Converted" or lead.converted_at is not None:
                if not lead.converted_contact_id or not lead.converted_company_id:
                    raise APIException(
                        status_code=409, message="Converted lead has missing customer links"
                    )
                result = self._conversion_result(lead)
                await db.commit()
                return result
            if lead.status != "Qualified" or lead.is_archived:
                raise APIException(
                    status_code=409, message="Only an active qualified lead can be converted"
                )
            if not lead.company.strip() or not lead.contact_name.strip() or not lead.email.strip():
                raise APIException(
                    status_code=422, message="Company, contact name and email are required"
                )
            companies, contacts = await self.repository.conversion_customers(
                db, organization_id, lead.company, lead.email
            )
            if len(companies) > 1 or len(contacts) > 1:
                raise APIException(
                    status_code=409, message="Resolve duplicate customers before conversion"
                )
            company = (
                companies[0]
                if companies
                else await CompanyRepository().create(
                    db,
                    data={
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "name": lead.company.strip(),
                        "industry": lead.industry,
                        "website": lead.website,
                    },
                )
            )
            await db.flush()
            contact = (
                contacts[0]
                if contacts
                else await ContactRepository().create(
                    db,
                    data={
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "name": lead.contact_name.strip(),
                        "email": lead.email.strip(),
                        "phone": lead.phone,
                        "company_id": company.id,
                    },
                )
            )
            if contact.company_id and contact.company_id != company.id:
                raise APIException(
                    status_code=409, message="Existing contact belongs to a different company"
                )
            await self.repository.link_conversion_contact(db, contact, company.id)
            await db.flush()
            deal = None
            if payload.create_deal:
                deal = await DealRepository().create(
                    db,
                    data={
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "title": payload.deal_title or lead.title,
                        "amount": payload.deal_amount or 0,
                        "stage": "Prospecting",
                        "assigned_to": current_user.id,
                        "company_id": company.id,
                        "contact_id": contact.id,
                    },
                )
                await db.flush()
            await self.repository.save_conversion(
                db,
                lead,
                company_id=company.id,
                contact_id=contact.id,
                deal_id=deal.id if deal else None,
                actor_id=current_user.id,
                converted_at=datetime.now(UTC),
            )
            result = self._conversion_result(lead)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    def _conversion_result(lead: Lead) -> dict:
        return {
            "message": "Lead converted successfully",
            "contact_id": lead.converted_contact_id,
            "company_id": lead.converted_company_id,
            "deal_id": lead.converted_deal_id,
        }

    async def assign_lead(
        self, db: AsyncSession, lead_id: str, user_id: str, *, organization_id: str
    ) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead.assigned_to = await self._resolve_assigned_to(db, user_id, organization_id)
        await self._commit(db, "Failed to assign lead")
        await notification_service.notify(
            db,
            event_name="lead.assigned",
            organization_id=lead.organization_id,
            entity_type="lead",
            entity_id=lead.id,
            assigned_to=lead.assigned_to,
            data={"id": lead.id, "title": lead.title, "assigned_to": lead.assigned_to},
        )
        return {"message": f"Lead {lead_id} assigned to user {user_id}", "status": "success"}

    async def get_timeline(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)

        timeline = [
            {
                "id": f"created-{lead.id}",
                "event_type": "lead_created",
                "title": "Lead Registered",
                "description": f"Lead '{lead.contact_name}' created from {lead.source}",
                "timestamp": str(lead.created_at),
            }
        ]

        for note in await self.repository.list_notes(db, lead_id):
            timeline.append(
                {
                    "id": f"note-{note.id}",
                    "event_type": "note_added",
                    "title": "Note Added",
                    "description": note.content,
                    "timestamp": str(note.created_at),
                }
            )

        for attachment in await self.repository.list_attachments(db, lead_id):
            timeline.append(
                {
                    "id": f"doc-{attachment.id}",
                    "event_type": "document_attached",
                    "title": "Document Attached",
                    "description": f"File '{attachment.filename}' uploaded to storage",
                    "timestamp": str(
                        getattr(attachment, "uploaded_at", getattr(attachment, "created_at", ""))
                    ),
                }
            )

        lead_tag = f"[Lead:{lead_id}]"
        for task in await self.repository.list_tasks(
            db, organization_id=lead.organization_id, lead_tag=lead_tag
        ):
            clean_desc = (
                (task.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
            )
            timeline.append(
                {
                    "id": f"task-{task.id}",
                    "event_type": "task_created",
                    "title": f"Task Created: {task.title}",
                    "description": (
                        clean_desc
                        if clean_desc
                        else f"Priority: {task.priority}, Status: {task.status}"
                    ),
                    "timestamp": str(task.created_at),
                }
            )

        for email in await self.repository.list_emails(
            db, organization_id=lead.organization_id, lead_tag=lead_tag
        ):
            timeline.append(
                {
                    "id": f"email-{email.id}",
                    "event_type": "email_sent",
                    "title": f"Email Sent: {email.subject}",
                    "description": f"Sent to {email.to_email}",
                    "timestamp": str(email.sent_at),
                }
            )

        contact_id = await self.repository.get_contact_id_by_email(
            db, lead.email, organization_id=organization_id
        )
        if contact_id:
            for call in await self.repository.list_calls(
                db, organization_id=lead.organization_id, lead_tag=lead_tag
            ):
                timeline.append(
                    {
                        "id": f"call-{call.id}",
                        "event_type": "call_logged",
                        "title": f"{call.call_type} Call Logged",
                        "description": call.notes or f"Duration: {call.duration_seconds} sec",
                        "timestamp": str(call.timestamp),
                    }
                )

        timeline.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return timeline

    async def get_notes(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        await self.require_lead(db, lead_id, organization_id=organization_id)
        notes = await self.repository.list_notes(db, lead_id)
        users_map = {}
        for user in await self.repository.list_users(db, organization_id=organization_id):
            name = (user.name or "").strip()
            users_map[user.id] = name if name else (user.email or "System User")
        return [
            {
                "id": note.id,
                "entity_type": "lead",
                "entity_id": lead_id,
                "content": note.content,
                "created_by": users_map.get(note.created_by, "System User"),
                "created_at": str(note.created_at),
            }
            for note in notes
        ]

    async def add_note(
        self,
        db: AsyncSession,
        lead_id: str,
        content: str,
        *,
        organization_id: str,
        actor_id: str,
    ) -> dict:
        await self.require_lead(db, lead_id, organization_id=organization_id)
        note = await self.repository.create_note(
            db, lead_id=lead_id, content=content, created_by=actor_id
        )
        await self._commit(db, "Failed to add note")
        return {
            "id": note.id,
            "entity_type": "lead",
            "entity_id": lead_id,
            "content": note.content,
            "created_by": note.created_by,
            "created_at": str(note.created_at),
        }

    async def get_tasks(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead_tag = f"[Lead:{lead_id}]"
        tasks = await self.repository.list_tasks(
            db, organization_id=lead.organization_id, lead_tag=lead_tag
        )
        output = []
        for task in tasks:
            clean_desc = (
                (task.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
            )
            output.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "description": clean_desc if clean_desc else None,
                    "priority": task.priority,
                    "due_date": str(task.due_date) if task.due_date else None,
                    "status": task.status,
                    "assigned_to": task.assigned_to,
                    "created_at": str(task.created_at),
                }
            )
        return output

    async def create_task(
        self,
        db: AsyncSession,
        lead_id: str,
        payload: TaskCreate,
        *,
        organization_id: str,
        actor_id: str,
    ) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        assigned_user_id = payload.assigned_to
        if not assigned_user_id:
            assigned_user_id = actor_id
        assigned_user_id = await self._resolve_assigned_to(db, assigned_user_id, organization_id)
        if not assigned_user_id:
            raise ForbiddenError(message="A valid same-organization task assignee is required.")

        due_dt = None
        if payload.due_date:
            try:
                due_dt = datetime.fromisoformat(payload.due_date)
            except Exception:
                due_dt = datetime.utcnow()
        else:
            due_dt = datetime.now(UTC)

        lead_tag = f"[Lead:{lead_id}]"
        raw_desc = payload.description or ""
        tagged_desc = f"{raw_desc}\n{lead_tag}" if raw_desc else lead_tag

        task = await self.repository.create_task(
            db,
            organization_id=lead.organization_id,
            title=payload.title,
            description=tagged_desc,
            priority=payload.priority or "Medium",
            status=payload.status or "Pending",
            due_date=due_dt,
            assigned_to=assigned_user_id,
        )
        await self._commit(db, "Failed to create task")
        await db.refresh(task)
        await notification_service.notify(
            db,
            event_name="task.created",
            organization_id=lead.organization_id,
            entity_type="task",
            entity_id=task.id,
            assigned_to=task.assigned_to,
            data={
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
                "due_date": str(task.due_date) if task.due_date else None,
                "assigned_to": task.assigned_to,
            },
        )
        return {
            "id": task.id,
            "title": task.title,
            "description": payload.description,
            "priority": task.priority,
            "due_date": str(task.due_date) if task.due_date else None,
            "status": task.status,
            "assigned_to": task.assigned_to,
            "created_at": str(task.created_at),
        }

    async def get_emails(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead_tag = f"[Lead:{lead_id}]"
        emails = await self.repository.list_emails(
            db, organization_id=lead.organization_id, lead_tag=lead_tag
        )
        return [
            {
                "id": email.id,
                "from_email": email.from_email,
                "to": [email.to_email],
                "subject": email.subject,
                "sent_at": str(email.sent_at),
            }
            for email in emails
        ]

    async def send_email(
        self,
        db: AsyncSession,
        lead_id: str,
        payload: EmailSendRequest,
        *,
        organization_id: str,
    ) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        to_addr = payload.to[0] if payload.to else lead.email
        lead_tag = f"[Lead:{lead_id}]"
        raw_body = payload.body or ""
        tagged_body = f"{raw_body}\n{lead_tag}" if raw_body else lead_tag

        email = await self.repository.create_email(
            db,
            organization_id=lead.organization_id,
            from_email="sales@enterprise-crm.com",
            to_email=str(to_addr),
            subject=payload.subject,
            body_text=tagged_body,
            status="sent",
        )
        await self._commit(db, "Failed to send email")
        await db.refresh(email)
        return {
            "id": email.id,
            "from_email": email.from_email,
            "to": [email.to_email],
            "subject": email.subject,
            "sent_at": str(email.sent_at),
        }

    async def get_calls(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead_tag = f"[Lead:{lead_id}]"
        calls = await self.repository.list_calls(
            db, organization_id=lead.organization_id, lead_tag=lead_tag
        )
        output = []
        for call in calls:
            clean_notes = (
                (call.notes or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
            )
            output.append(
                {
                    "id": call.id,
                    "contact_id": lead_id,
                    "call_type": call.call_type,
                    "duration_seconds": call.duration_seconds,
                    "notes": clean_notes if clean_notes else None,
                    "timestamp": str(call.timestamp),
                }
            )
        return output

    async def log_call(
        self,
        db: AsyncSession,
        lead_id: str,
        payload: CallLogBase,
        *,
        organization_id: str,
    ) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        if not lead.email:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Lead email is required before logging a call",
            )
        contact_id = await self.repository.get_contact_id_by_email(
            db, lead.email, organization_id=organization_id
        )
        if not contact_id:
            contact = await self.repository.create_contact(
                db,
                name=lead.contact_name or "Unknown Lead",
                email=lead.email,
                organization_id=lead.organization_id,
            )
            await db.flush()
            contact_id = contact.id

        lead_tag = f"[Lead:{lead_id}]"
        raw_notes = payload.notes or ""
        tagged_notes = f"{raw_notes}\n{lead_tag}" if raw_notes else lead_tag

        call = await self.repository.create_call(
            db,
            organization_id=lead.organization_id,
            contact_id=contact_id,
            call_type=payload.call_type or "Outbound",
            duration_seconds=payload.duration_seconds or 0,
            notes=tagged_notes,
        )
        await self._commit(db, "Failed to log call")
        await db.refresh(call)
        return {
            "id": call.id,
            "contact_id": lead_id,
            "call_type": call.call_type,
            "duration_seconds": call.duration_seconds,
            "notes": payload.notes,
            "timestamp": str(call.timestamp),
        }

    async def get_documents(
        self, db: AsyncSession, lead_id: str, *, organization_id: str
    ) -> list[dict]:
        await self.require_lead(db, lead_id, organization_id=organization_id)
        attachments = await self.repository.list_attachments(db, lead_id)
        output = []
        for attachment in attachments:
            download_proxy = f"/api/v1/leads/{lead_id}/documents/{attachment.id}/download"
            output.append(
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "file_size": attachment.file_size or 0,
                    "mime_type": attachment.mime_type or "application/pdf",
                    "download_url": download_proxy,
                    "uploaded_at": str(
                        getattr(attachment, "uploaded_at", getattr(attachment, "created_at", ""))
                    ),
                }
            )
        return output

    async def download_document(
        self, db: AsyncSession, lead_id: str, document_id: str, current_user: User
    ) -> tuple[bytes, str, str]:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            raise ForbiddenError(message="Organization context is required.")
        lead = await self.repository.get_by_id_for_org(db, lead_id, organization_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")

        attachment = await self.repository.get_attachment_for_lead(db, document_id, lead_id)
        if not attachment:
            raise NotFoundError(message="Document attachment record not found")

        file_bytes: bytes | None = None
        possible_keys = [f"leads/{lead_id}/{attachment.filename}", attachment.filename]
        if attachment.file_url:
            clean_url = attachment.file_url.split("?")[0]
            if "leads/" in clean_url:
                possible_keys.insert(0, "leads/" + clean_url.split("leads/")[-1])

        last_error: Exception | None = None
        for key in dict.fromkeys(possible_keys):
            try:
                file_bytes = await asyncio.to_thread(_read_s3_object, key)
                if file_bytes:
                    break
            except Exception as exc:
                last_error = exc

        if not file_bytes:
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Document content is unavailable. Please try again later.",
            ) from last_error

        return file_bytes, attachment.mime_type or "application/octet-stream", attachment.filename

    async def upload_document(
        self, db: AsyncSession, lead_id: str, file: UploadFile, current_user: User
    ) -> dict:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            raise ForbiddenError(message="Organization context is required.")
        lead = await self.repository.get_by_id_for_org(db, lead_id, organization_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")

        safe_filename = _sanitize_filename(file.filename)
        _, extension = _split_extension(safe_filename)
        max_size = int(getattr(settings, "MAX_DOCUMENT_UPLOAD_SIZE", 0) or 0)
        declared_size = getattr(file, "size", None)
        _validate_upload(safe_filename, file.content_type, declared_size)
        contents = await _read_upload_with_limit(file, max_size)
        file_size = len(contents)
        object_name = f"leads/{lead_id}/{uuid.uuid4().hex}{extension}"

        try:
            s3_key = await asyncio.to_thread(
                s3_service.upload_file,
                io.BytesIO(contents),
                object_name=object_name,
                content_type=_normalize_mime_type(file.content_type),
            )
            presigned_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
        except Exception as exc:
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to upload document to storage. Please try again later.",
            ) from exc

        attachment = await self.repository.create_attachment(
            db,
            lead_id=lead_id,
            filename=safe_filename,
            file_url=presigned_url,
            file_size=file_size,
            mime_type=_normalize_mime_type(file.content_type),
        )
        await self._commit(db, "Failed to upload lead document")
        await db.refresh(attachment)
        download_proxy = f"/api/v1/leads/{lead_id}/documents/{attachment.id}/download"
        return {
            "id": attachment.id,
            "filename": attachment.filename,
            "file_size": attachment.file_size or 0,
            "mime_type": attachment.mime_type or "application/pdf",
            "download_url": download_proxy,
            "uploaded_at": str(
                getattr(attachment, "uploaded_at", getattr(attachment, "created_at", ""))
            ),
        }

    async def archive_lead(self, db: AsyncSession, lead_id: str, *, organization_id: str) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead.is_archived = True
        await self._commit(db, "Failed to archive lead")
        return {"message": f"Lead {lead_id} archived", "status": "success"}

    async def unarchive_lead(self, db: AsyncSession, lead_id: str, *, organization_id: str) -> dict:
        lead = await self.require_lead(db, lead_id, organization_id=organization_id)
        lead.is_archived = False
        await self._commit(db, "Failed to unarchive lead")
        return {"message": f"Lead {lead_id} restored", "status": "success"}


lead_service = LeadService()
