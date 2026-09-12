from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Email, EmailTemplate


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
        stmt = (
            stmt.order_by(Email.created_at.desc(), Email.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_emails(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(Email).where(Email.organization_id == organization_id)
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where((Email.subject.ilike(term)) | (Email.to_email.ilike(term)))
        return int((await db.execute(stmt)).scalar_one())

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], organization_id: str
    ) -> Sequence[Email]:
        stmt = select(Email).where(Email.id.in_(ids), Email.organization_id == organization_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    def _for_contact_query(
        *, organization_id: str, contact_id: str, recipient_email: str
    ):
        """Match explicit relationships plus unlinked legacy recipient rows.

        An email explicitly linked to a different contact is never reassigned by
        address matching. The recipient fallback exists for historical delivery
        records that predate ``emails.contact_id``.
        """
        normalized_recipient = func.lower(func.trim(recipient_email))
        matching_contact_count = (
            select(func.count(Contact.id))
            .where(
                Contact.organization_id == organization_id,
                func.lower(func.trim(Contact.email)) == normalized_recipient,
            )
            .scalar_subquery()
        )
        return select(Email).where(
            Email.organization_id == organization_id,
            or_(
                Email.contact_id == contact_id,
                and_(
                    Email.contact_id.is_(None),
                    func.lower(func.trim(Email.to_email)) == normalized_recipient,
                    matching_contact_count == 1,
                ),
            ),
        )

    async def list_for_contact(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        contact_id: str,
        recipient_email: str,
        limit: int | None = None,
        offset: int = 0,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ) -> Sequence[Email]:
        stmt = self._for_contact_query(
            organization_id=organization_id,
            contact_id=contact_id,
            recipient_email=recipient_email,
        )
        if statuses:
            stmt = stmt.where(Email.status.in_(statuses))
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Email.subject.ilike(term),
                    Email.from_email.ilike(term),
                    Email.to_email.ilike(term),
                )
            )
        stmt = stmt.order_by(
            func.coalesce(Email.sent_at, Email.created_at).desc(), Email.id.desc()
        ).offset(max(0, offset))
        if limit is not None:
            stmt = stmt.limit(limit)
        return (await db.execute(stmt)).scalars().all()

    async def count_for_contact(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        contact_id: str,
        recipient_email: str,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ) -> int:
        base = self._for_contact_query(
            organization_id=organization_id,
            contact_id=contact_id,
            recipient_email=recipient_email,
        )
        if statuses:
            base = base.where(Email.status.in_(statuses))
        if search and search.strip():
            term = f"%{search.strip()}%"
            base = base.where(
                or_(
                    Email.subject.ilike(term),
                    Email.from_email.ilike(term),
                    Email.to_email.ilike(term),
                )
            )
        return int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)

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

    async def list_drafts(self, db: AsyncSession, *, organization_id: str) -> Sequence[Email]:
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
        stmt = (
            select(EmailTemplate).where(EmailTemplate.organization_id == organization_id).limit(20)
        )
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
