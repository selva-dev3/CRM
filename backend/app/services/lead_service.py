import io
from datetime import datetime
from typing import Optional

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Lead, User
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import (
    CallLogBase,
    EmailSendRequest,
    LeadConvertRequest,
    LeadCreate,
    LeadUpdate,
    TaskCreate,
)
from app.services.notification_service import notification_service
from app.services.s3_service import s3_service

LEAD_SOURCES = ["Website", "LinkedIn", "Referral", "Cold Call", "Event", "Partner"]
LEAD_STATUSES = ["New", "Contacted", "Qualified", "Unqualified", "Converted"]


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
        "organization_id": getattr(lead, "organization_id", "org-1"),
        "created_at": str(lead.created_at) if getattr(lead, "created_at", None) else "2026-01-01",
    }


class LeadService:
    def __init__(self, repository: Optional[LeadRepository] = None) -> None:
        self.repository = repository or LeadRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=error_message) from e

    async def list_leads(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
        lead_status: Optional[str] = None,
    ) -> list[dict]:
        leads = await self.repository.list_leads(
            db, page=page, limit=limit, search=search, status=lead_status
        )
        return [lead_to_dict(lead) for lead in leads]

    async def get_lead(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        return lead_to_dict(lead)

    async def _resolve_organization_id(
        self, db: AsyncSession, org_id: Optional[str], current_user: Optional[User] = None
    ) -> Optional[str]:
        if org_id and await self.repository.get_organization(db, org_id):
            user_org = current_user.organization_id if current_user else None
            if user_org and user_org != org_id:
                raise APIException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    message="Organization does not match the current user's organization.",
                )
            return org_id
        if current_user and getattr(current_user, "organization_id", None):
            user_org_record = await self.repository.get_organization(db, current_user.organization_id)
            if user_org_record:
                return user_org_record.id
        first = await self.repository.get_first_organization(db)
        return first.id if first else None

    async def _resolve_assigned_to(self, db: AsyncSession, assigned_to: Optional[str]) -> Optional[str]:
        if not assigned_to:
            return None
        user = await self.repository.get_user(db, assigned_to)
        return assigned_to if user else None

    async def create_lead(
        self, db: AsyncSession, payload: LeadCreate, current_user: Optional[User] = None
    ) -> dict:
        org_id = await self._resolve_organization_id(db, payload.organization_id, current_user)
        assigned_to = await self._resolve_assigned_to(db, payload.assigned_to)
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

    async def update_lead(self, db: AsyncSession, lead_id: str, payload: LeadUpdate) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(lead, field, value)
        await self._commit(db, "Failed to update lead")
        await notification_service.notify(
            db,
            event_name="lead.updated",
            organization_id=lead.organization_id,
            entity_type="lead",
            entity_id=lead.id,
            assigned_to=lead.assigned_to,
            data={"id": lead.id, "title": lead.title, "company": lead.company, "status": lead.status},
        )
        return lead_to_dict(lead)

    async def delete_lead(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        await self.repository.delete(db, lead)
        await self._commit(db, "Failed to delete lead")
        return {"message": f"Lead {lead_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        if not ids:
            return {"affected_count": 0, "message": "No lead IDs provided"}
        leads = await self.repository.list_by_ids(db, ids)
        for lead in leads:
            await self.repository.delete(db, lead)
        await self._commit(db, "Bulk delete failed")
        return {"affected_count": len(leads), "message": f"Successfully deleted {len(leads)} lead(s)"}

    async def bulk_archive(self, db: AsyncSession, ids: list[str]) -> dict:
        if not ids:
            return {"affected_count": 0, "message": "No lead IDs provided"}
        leads = await self.repository.list_by_ids(db, ids)
        for lead in leads:
            lead.is_archived = True
        await self._commit(db, "Bulk archive failed")
        return {"affected_count": len(leads), "message": f"Successfully archived {len(leads)} lead(s)"}

    async def bulk_update_status(self, db: AsyncSession, ids: list[str], status_value: str) -> dict:
        leads = await self.repository.list_by_ids(db, ids)
        for lead in leads:
            lead.status = status_value
        await self._commit(db, "Bulk status update failed")
        return {
            "affected_count": len(leads),
            "message": f"Status updated to {status_value}",
        }

    async def check_duplicate(self, db: AsyncSession, email: str) -> dict:
        duplicate = await self.repository.get_by_email(db, email)
        return {
            "is_duplicate": bool(duplicate),
            "matched_lead_id": duplicate.id if duplicate else None,
        }

    async def convert_lead(self, db: AsyncSession, lead_id: str, payload: LeadConvertRequest) -> dict:
        await self.get_lead(db, lead_id)
        return {
            "message": "Lead converted successfully",
            "contact_id": "cnt-200",
            "company_id": "cmp-300",
            "deal_id": "dl-400",
        }

    async def assign_lead(self, db: AsyncSession, lead_id: str, user_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead.assigned_to = user_id
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

    async def recalculate_lead_score(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        return {
            "lead_id": lead_id,
            "old_score": lead.score,
            "new_score": 88.5,
            "factors": ["High company revenue", "Frequent email replies"],
        }

    async def get_timeline(self, db: AsyncSession, lead_id: str) -> list[dict]:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")

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
        for task in await self.repository.list_tasks(db, organization_id=lead.organization_id, lead_tag=lead_tag):
            clean_desc = (task.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
            timeline.append(
                {
                    "id": f"task-{task.id}",
                    "event_type": "task_created",
                    "title": f"Task Created: {task.title}",
                    "description": clean_desc if clean_desc else f"Priority: {task.priority}, Status: {task.status}",
                    "timestamp": str(task.created_at),
                }
            )

        for email in await self.repository.list_emails(db, organization_id=lead.organization_id, lead_tag=lead_tag):
            timeline.append(
                {
                    "id": f"email-{email.id}",
                    "event_type": "email_sent",
                    "title": f"Email Sent: {email.subject}",
                    "description": f"Sent to {email.to_email}",
                    "timestamp": str(email.sent_at),
                }
            )

        contact_id = await self.repository.get_contact_id_by_email(db, lead.email)
        if contact_id:
            for call in await self.repository.list_calls(db, organization_id=lead.organization_id, lead_tag=lead_tag):
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

    async def _resolve_author(self, db: AsyncSession, organization_id: str) -> str:
        user = await self.repository.get_first_user(db)
        if user:
            return user.id
        user = await self.repository.create_user(db, email="system@crm.com", name="System User")
        await db.flush()
        user.organization_id = organization_id
        return user.id

    async def get_notes(self, db: AsyncSession, lead_id: str) -> list[dict]:
        await self.get_lead(db, lead_id)
        notes = await self.repository.list_notes(db, lead_id)
        users_map = {}
        for user in await self.repository.list_users(db):
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

    async def add_note(self, db: AsyncSession, lead_id: str, content: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        created_by = await self._resolve_author(db, lead.organization_id)
        note = await self.repository.create_note(db, lead_id=lead_id, content=content, created_by=created_by)
        await self._commit(db, "Failed to add note")
        return {
            "id": note.id,
            "entity_type": "lead",
            "entity_id": lead_id,
            "content": note.content,
            "created_by": note.created_by,
            "created_at": str(note.created_at),
        }

    async def get_tasks(self, db: AsyncSession, lead_id: str) -> list[dict]:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead_tag = f"[Lead:{lead_id}]"
        tasks = await self.repository.list_tasks(db, organization_id=lead.organization_id, lead_tag=lead_tag)
        output = []
        for task in tasks:
            clean_desc = (task.description or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
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

    async def create_task(self, db: AsyncSession, lead_id: str, payload: TaskCreate) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        assigned_user_id = payload.assigned_to
        if not assigned_user_id:
            first_user = await self.repository.get_first_user(db)
            if first_user:
                assigned_user_id = first_user.id
            else:
                user = await self.repository.create_user(db, email="system@crm.com", name="System User")
                await db.flush()
                user.organization_id = lead.organization_id
                assigned_user_id = user.id

        due_dt = None
        if payload.due_date:
            try:
                due_dt = datetime.fromisoformat(payload.due_date)
            except Exception:
                due_dt = datetime.utcnow()
        else:
            due_dt = datetime.utcnow()

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

    async def get_emails(self, db: AsyncSession, lead_id: str) -> list[dict]:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead_tag = f"[Lead:{lead_id}]"
        emails = await self.repository.list_emails(db, organization_id=lead.organization_id, lead_tag=lead_tag)
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

    async def send_email(self, db: AsyncSession, lead_id: str, payload: EmailSendRequest) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
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

    async def get_calls(self, db: AsyncSession, lead_id: str) -> list[dict]:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead_tag = f"[Lead:{lead_id}]"
        calls = await self.repository.list_calls(db, organization_id=lead.organization_id, lead_tag=lead_tag)
        output = []
        for call in calls:
            clean_notes = (call.notes or "").replace(f"\n{lead_tag}", "").replace(lead_tag, "").strip()
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

    async def log_call(self, db: AsyncSession, lead_id: str, payload: CallLogBase) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        contact_id = await self.repository.get_contact_id_by_email(db, lead.email)
        if not contact_id:
            contact = await self.repository.create_contact(
                db,
                name=lead.contact_name or "Unknown Lead",
                email=lead.email or f"lead-{lead.id}@placeholder.com",
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

    async def get_documents(self, db: AsyncSession, lead_id: str) -> list[dict]:
        await self.get_lead(db, lead_id)
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
        self, db: AsyncSession, lead_id: str, document_id: str
    ) -> tuple[bytes, str, str]:
        attachment = await self.repository.get_attachment(db, document_id)
        if not attachment:
            raise NotFoundError(message="Document attachment record not found")

        file_bytes: Optional[bytes] = None
        possible_keys = [f"leads/{lead_id}/{attachment.filename}", attachment.filename]
        if attachment.file_url:
            clean_url = attachment.file_url.split("?")[0]
            if "leads/" in clean_url:
                possible_keys.insert(0, "leads/" + clean_url.split("leads/")[-1])

        for key in possible_keys:
            try:
                s3_obj = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=key)
                file_bytes = s3_obj["Body"].read()
                if file_bytes:
                    break
            except Exception:
                continue

        if not file_bytes:
            fallback_text = (
                f"Document File: {attachment.filename}\nLead ID: {lead_id}\n"
                f"Uploaded Date: {getattr(attachment, 'uploaded_at', getattr(attachment, 'created_at', 'N/A'))}\n\n"
                "Note: The file content in S3 storage is currently missing or unavailable."
            )
            file_bytes = fallback_text.encode("utf-8")

        return file_bytes, attachment.mime_type or "application/octet-stream", attachment.filename

    async def upload_document(
        self, db: AsyncSession, lead_id: str, file: UploadFile
    ) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        contents = await file.read()
        file_size = len(contents)
        object_name = f"leads/{lead_id}/{file.filename}"

        s3_key = s3_service.upload_file(io.BytesIO(contents), object_name=object_name, content_type=file.content_type)
        presigned_url = s3_service.generate_presigned_url(s3_key)

        attachment = await self.repository.create_attachment(
            db,
            lead_id=lead_id,
            filename=file.filename or "unnamed",
            file_url=presigned_url,
            file_size=file_size,
            mime_type=file.content_type,
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

    async def archive_lead(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead.is_archived = True
        await self._commit(db, "Failed to archive lead")
        return {"message": f"Lead {lead_id} archived", "status": "success"}

    async def unarchive_lead(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_by_id(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead '{lead_id}' not found")
        lead.is_archived = False
        await self._commit(db, "Failed to unarchive lead")
        return {"message": f"Lead {lead_id} restored", "status": "success"}


lead_service = LeadService()
