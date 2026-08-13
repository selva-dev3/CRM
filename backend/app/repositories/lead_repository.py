from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CallLog,
    Contact,
    Email,
    Lead,
    LeadAttachment,
    LeadNote,
    Organization,
    Task,
    User,
)


class LeadRepository:
    """DB query layer for the Lead domain (including its notes/attachments
    and the related task/email/call records used to build a lead timeline).
    No business logic lives here.
    """

    async def list_leads(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Lead]:
        stmt = select(Lead)

        if isinstance(search, str) and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                Lead.contact_name.ilike(pattern)
                | Lead.company.ilike(pattern)
                | Lead.title.ilike(pattern)
                | Lead.email.ilike(pattern)
                | Lead.phone.ilike(pattern)
            )

        if isinstance(status, str) and status.strip():
            stmt = stmt.where(Lead.status == status.strip())

        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, lead_id: str) -> Optional[Lead]:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        return result.scalars().first()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[Lead]:
        result = await db.execute(select(Lead).where(Lead.id.in_(ids)))
        return list(result.scalars().all())

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Lead]:
        result = await db.execute(select(Lead).where(Lead.email == email))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> Lead:
        lead = Lead(**data)
        db.add(lead)
        return lead

    async def delete(self, db: AsyncSession, lead: Lead) -> None:
        await db.delete(lead)

    async def list_notes(self, db: AsyncSession, lead_id: str) -> list[LeadNote]:
        result = await db.execute(select(LeadNote).where(LeadNote.lead_id == lead_id))
        return list(result.scalars().all())

    async def create_note(
        self, db: AsyncSession, *, lead_id: str, content: str, created_by: str
    ) -> LeadNote:
        note = LeadNote(lead_id=lead_id, content=content, created_by=created_by)
        db.add(note)
        return note

    async def list_attachments(self, db: AsyncSession, lead_id: str) -> list[LeadAttachment]:
        result = await db.execute(
            select(LeadAttachment).where(LeadAttachment.lead_id == lead_id)
        )
        return list(result.scalars().all())

    async def get_attachment(
        self, db: AsyncSession, attachment_id: str
    ) -> Optional[LeadAttachment]:
        result = await db.execute(
            select(LeadAttachment).where(LeadAttachment.id == attachment_id)
        )
        return result.scalars().first()

    async def create_attachment(
        self,
        db: AsyncSession,
        *,
        lead_id: str,
        filename: str,
        file_url: str,
        file_size: Optional[int],
        mime_type: Optional[str],
    ) -> LeadAttachment:
        attachment = LeadAttachment(
            lead_id=lead_id,
            filename=filename,
            file_url=file_url,
            file_size=file_size,
            mime_type=mime_type,
        )
        db.add(attachment)
        return attachment

    async def list_tasks(
        self, db: AsyncSession, *, organization_id: str, lead_tag: str
    ) -> list[Task]:
        result = await db.execute(
            select(Task).where(
                Task.organization_id == organization_id,
                Task.description.contains(lead_tag),
            )
        )
        return list(result.scalars().all())

    async def create_task(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        title: str,
        description: Optional[str],
        priority: str,
        status: str,
        due_date: datetime,
        assigned_to: str,
    ) -> Task:
        task = Task(
            organization_id=organization_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
            assigned_to=assigned_to,
        )
        db.add(task)
        return task

    async def list_emails(
        self, db: AsyncSession, *, organization_id: str, lead_tag: str
    ) -> list[Email]:
        result = await db.execute(
            select(Email).where(
                Email.organization_id == organization_id,
                Email.body_text.contains(lead_tag),
            )
        )
        return list(result.scalars().all())

    async def create_email(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        from_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        status: str,
    ) -> Email:
        email = Email(
            organization_id=organization_id,
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            status=status,
        )
        db.add(email)
        return email

    async def list_calls(
        self, db: AsyncSession, *, organization_id: str, lead_tag: str
    ) -> list[CallLog]:
        result = await db.execute(
            select(CallLog).where(
                CallLog.organization_id == organization_id,
                CallLog.notes.contains(lead_tag),
            )
        )
        return list(result.scalars().all())

    async def create_call(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        contact_id: str,
        call_type: str,
        duration_seconds: int,
        notes: Optional[str],
    ) -> CallLog:
        call = CallLog(
            organization_id=organization_id,
            contact_id=contact_id,
            call_type=call_type,
            duration_seconds=duration_seconds,
            notes=notes,
        )
        db.add(call)
        return call

    async def get_organization(self, db: AsyncSession, org_id: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalars().first()

    async def get_first_organization(self, db: AsyncSession) -> Optional[Organization]:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def get_user(self, db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_first_user(self, db: AsyncSession) -> Optional[User]:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def list_users(self, db: AsyncSession) -> list[User]:
        result = await db.execute(select(User))
        return list(result.scalars().all())

    async def create_user(self, db: AsyncSession, *, email: str, name: str) -> User:
        user = User(
            email=email,
            hashed_password="hashed_password_placeholder",
            name=name,
        )
        db.add(user)
        return user

    async def get_contact_id_by_email(
        self, db: AsyncSession, email: str
    ) -> Optional[str]:
        result = await db.execute(select(Contact.id).where(Contact.email == email).limit(1))
        return result.scalars().first()

    async def create_contact(
        self, db: AsyncSession, *, name: str, email: str, organization_id: str
    ) -> Contact:
        contact = Contact(name=name, email=email, organization_id=organization_id)
        db.add(contact)
        return contact