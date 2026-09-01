from collections.abc import Sequence

from sqlalchemy import select
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
        search: str | None = None,
    ) -> Sequence[Email]:
        stmt = select(Email)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where((Email.subject.ilike(term)) | (Email.to_email.ilike(term)))
        stmt = stmt.order_by(Email.sent_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> Sequence[Email]:
        stmt = select(Email).where(Email.id.in_(ids))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def create_email(self, db: AsyncSession, *, data: dict) -> Email:
        email = Email(**data)
        db.add(email)
        return email

    async def delete(self, db: AsyncSession, email: Email) -> None:
        await db.delete(email)

    async def list_templates(self, db: AsyncSession) -> Sequence[EmailTemplate]:
        stmt = select(EmailTemplate).limit(20)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def create_template(self, db: AsyncSession, *, data: dict) -> EmailTemplate:
        template = EmailTemplate(**data)
        db.add(template)
        return template

    async def get_template(self, db: AsyncSession, template_id: str) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(EmailTemplate.id == template_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def delete_template(self, db: AsyncSession, template: EmailTemplate) -> None:
        await db.delete(template)
