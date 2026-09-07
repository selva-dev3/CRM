from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Email, EmailTemplate


class EmailRepository:
    """Query layer for the Email / EmailTemplate domains — no business logic."""

    async def list_emails(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        search: str | None = None,
    ) -> Sequence[Email]:
        stmt = select(Email).where(Email.organization_id == organization_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where((Email.subject.ilike(term)) | (Email.to_email.ilike(term)))
        stmt = stmt.order_by(Email.created_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], organization_id: str
    ) -> Sequence[Email]:
        stmt = select(Email).where(
            Email.id.in_(ids), Email.organization_id == organization_id
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_by_recipient(
        self, db: AsyncSession, *, organization_id: str, recipient_email: str
    ) -> Sequence[Email]:
        result = await db.execute(
            select(Email)
            .where(
                Email.organization_id == organization_id,
                func.lower(Email.to_email) == recipient_email.strip().lower(),
            )
            .order_by(Email.sent_at.desc())
        )
        return result.scalars().all()

    async def create_email(self, db: AsyncSession, *, data: dict) -> Email:
        email = Email(**data)
        db.add(email)
        return email

    async def get_email(
        self, db: AsyncSession, *, email_id: str, organization_id: str
    ) -> Email | None:
        result = await db.execute(
            select(Email).where(
                Email.id == email_id,
                Email.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_by_idempotency_key(
        self, db: AsyncSession, *, organization_id: str, idempotency_key: str
    ) -> Email | None:
        result = await db.execute(
            select(Email).where(
                Email.organization_id == organization_id,
                Email.idempotency_key == idempotency_key,
            )
        )
        return result.scalars().first()

    async def list_drafts(
        self, db: AsyncSession, *, organization_id: str
    ) -> Sequence[Email]:
        result = await db.execute(
            select(Email)
            .where(Email.organization_id == organization_id, Email.status == "Draft")
            .order_by(Email.updated_at.desc())
            .limit(100)
        )
        return result.scalars().all()

    async def expire_delivery_claims(self, db: AsyncSession, now: datetime) -> None:
        await db.execute(
            update(Email)
            .where(
                Email.status == "Processing",
                Email.claimed_until.is_not(None),
                Email.claimed_until < now,
            )
            .values(
                status="Unknown",
                claimed_until=None,
                failure_reason="Delivery worker stopped after provider processing began",
            )
        )

    async def claim_delivery(self, db: AsyncSession, now: datetime) -> Email | None:
        result = await db.execute(
            select(Email)
            .where(Email.status == "Pending")
            .order_by(Email.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        email = result.scalars().first()
        if email:
            email.status = "Processing"
            email.delivery_attempts += 1
            email.last_attempt_at = now
            email.claimed_until = now + timedelta(minutes=5)
            email.failure_reason = None
        return email

    async def record_delivery_result(
        self,
        db: AsyncSession,
        email: Email,
        *,
        status: str,
        provider_message_id: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        email.status = status
        email.provider_message_id = provider_message_id
        email.failure_reason = failure_reason
        email.claimed_until = None
        if status == "Sent":
            email.sent_at = datetime.now(UTC)

    async def retry_failed(
        self, db: AsyncSession, *, email_id: str, organization_id: str
    ) -> Email | None:
        result = await db.execute(
            select(Email)
            .where(
                Email.id == email_id,
                Email.organization_id == organization_id,
            )
            .with_for_update()
        )
        email = result.scalars().first()
        if email and email.status == "Failed":
            email.status = "Pending"
            email.failure_reason = None
            email.claimed_until = None
        return email

    async def delete(self, db: AsyncSession, email: Email) -> None:
        await db.delete(email)

    async def list_templates(
        self, db: AsyncSession, organization_id: str
    ) -> Sequence[EmailTemplate]:
        stmt = select(EmailTemplate).where(
            EmailTemplate.organization_id == organization_id
        ).limit(20)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def create_template(self, db: AsyncSession, *, data: dict) -> EmailTemplate:
        template = EmailTemplate(**data)
        db.add(template)
        return template

    async def get_template(
        self, db: AsyncSession, template_id: str, organization_id: str
    ) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == organization_id,
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def delete_template(self, db: AsyncSession, template: EmailTemplate) -> None:
        await db.delete(template)
