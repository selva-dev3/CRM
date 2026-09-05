from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

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
from app.models.audit import AuditLog
from app.models.company import Company
from app.models.deal import DealActivity
from app.models.lead import LeadActivity


class LeadRepository:
    """DB query layer for the Lead domain (including its notes/attachments
    and the related task/email/call records used to build a lead timeline).
    No business logic lives here.
    """

    async def lock_conversion(self, db: AsyncSession, lead_id: str, organization_id: str):
        # Serialize conversions within a tenant, including customer deduplication.
        await db.execute(
            select(Organization.id).where(Organization.id == organization_id).with_for_update()
        )
        result = await db.execute(
            select(Lead)
            .where(Lead.id == lead_id, Lead.organization_id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def conversion_customers(
        self, db: AsyncSession, organization_id: str, company_name: str, email: str
    ):
        companies = await db.execute(
            select(Company)
            .where(
                Company.organization_id == organization_id,
                func.lower(func.trim(Company.name)) == company_name.strip().lower(),
            )
            .limit(2)
        )
        contacts = await db.execute(
            select(Contact)
            .where(
                Contact.organization_id == organization_id,
                func.lower(func.trim(Contact.email)) == email.strip().lower(),
            )
            .limit(2)
        )
        return list(companies.scalars().all()), list(contacts.scalars().all())

    async def save_conversion(
        self,
        db: AsyncSession,
        lead: Lead,
        *,
        company_id: str,
        contact_id: str,
        deal_id: str | None,
        actor_id: str,
        converted_at: datetime,
    ) -> None:
        lead.converted_company_id = company_id
        lead.converted_contact_id = contact_id
        lead.converted_deal_id = deal_id
        lead.converted_at = converted_at
        lead.status = "Converted"
        db.add(LeadActivity(lead_id=lead.id, action="Lead converted", performed_by=actor_id))
        if deal_id:
            db.add(
                DealActivity(
                    deal_id=deal_id,
                    action=f"Deal created from lead {lead.id}",
                    performed_by=actor_id,
                )
            )
        db.add(
            AuditLog(
                organization_id=lead.organization_id,
                user_id=actor_id,
                action="lead.converted",
                details=lead.id,
            )
        )

    async def record_qualification(self, db: AsyncSession, lead: Lead, *, actor_id: str) -> None:
        db.add(
            LeadActivity(
                lead_id=lead.id,
                action="Lead qualified",
                performed_by=actor_id,
            )
        )
        db.add(
            AuditLog(
                organization_id=lead.organization_id,
                user_id=actor_id,
                action="lead.qualified",
                details=lead.id,
            )
        )

    async def link_conversion_contact(
        self, db: AsyncSession, contact: Contact, company_id: str
    ) -> None:
        contact.company_id = company_id

    @staticmethod
    def _list_filters(
        *, search: str | None = None, status: str | None = None
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []

        if isinstance(search, str) and search.strip():
            pattern = f"%{search.strip()}%"
            filters.append(
                Lead.contact_name.ilike(pattern)
                | Lead.company.ilike(pattern)
                | Lead.title.ilike(pattern)
                | Lead.email.ilike(pattern)
                | Lead.phone.ilike(pattern)
            )

        if isinstance(status, str) and status.strip():
            filters.append(func.lower(Lead.status) == status.strip().lower())

        return filters

    async def list_leads(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        search: str | None = None,
        status: str | None = None,
    ) -> list[Lead]:
        stmt = (
            select(Lead)
            .where(
                Lead.organization_id == organization_id,
                *self._list_filters(search=search, status=status),
            )
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_leads(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.organization_id == organization_id,
                *self._list_filters(search=search, status=status),
            )
        )
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id(self, db: AsyncSession, lead_id: str) -> Lead | None:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        return result.scalars().first()

    async def get_by_id_for_org(
        self, db: AsyncSession, lead_id: str, organization_id: str
    ) -> Lead | None:
        result = await db.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], *, organization_id: str
    ) -> list[Lead]:
        result = await db.execute(
            select(Lead).where(Lead.id.in_(ids), Lead.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def get_by_email(
        self, db: AsyncSession, email: str, *, organization_id: str
    ) -> Lead | None:
        result = await db.execute(
            select(Lead).where(Lead.email == email, Lead.organization_id == organization_id)
        )
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
        result = await db.execute(select(LeadAttachment).where(LeadAttachment.lead_id == lead_id))
        return list(result.scalars().all())

    async def get_attachment(self, db: AsyncSession, attachment_id: str) -> LeadAttachment | None:
        result = await db.execute(select(LeadAttachment).where(LeadAttachment.id == attachment_id))
        return result.scalars().first()

    async def get_attachment_for_lead(
        self, db: AsyncSession, attachment_id: str, lead_id: str
    ) -> LeadAttachment | None:
        result = await db.execute(
            select(LeadAttachment).where(
                LeadAttachment.id == attachment_id,
                LeadAttachment.lead_id == lead_id,
            )
        )
        return result.scalars().first()

    async def create_attachment(
        self,
        db: AsyncSession,
        *,
        lead_id: str,
        filename: str,
        file_url: str,
        file_size: int | None,
        mime_type: str | None,
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
        description: str | None,
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
        notes: str | None,
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

    async def get_organization(self, db: AsyncSession, org_id: str) -> Organization | None:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalars().first()

    async def get_first_organization(self, db: AsyncSession) -> Organization | None:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def get_user(self, db: AsyncSession, user_id: str) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_first_user(self, db: AsyncSession, *, organization_id: str) -> User | None:
        result = await db.execute(
            select(User).where(User.organization_id == organization_id).limit(1)
        )
        return result.scalars().first()

    async def list_users(self, db: AsyncSession, *, organization_id: str) -> list[User]:
        result = await db.execute(select(User).where(User.organization_id == organization_id))
        return list(result.scalars().all())

    async def create_user(
        self, db: AsyncSession, *, email: str, name: str, hashed_password: str
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            name=name,
        )
        db.add(user)
        return user

    async def get_contact_id_by_email(
        self, db: AsyncSession, email: str, *, organization_id: str
    ) -> str | None:
        result = await db.execute(
            select(Contact.id)
            .where(
                Contact.email == email,
                Contact.organization_id == organization_id,
            )
            .limit(1)
        )
        return result.scalars().first()

    async def create_contact(
        self, db: AsyncSession, *, name: str, email: str, organization_id: str
    ) -> Contact:
        contact = Contact(name=name, email=email, organization_id=organization_id)
        db.add(contact)
        return contact
