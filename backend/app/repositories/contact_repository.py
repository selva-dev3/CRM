from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact


class ContactRepository:
    """DB query layer for the Contact entity. No business logic here."""

    async def list_by_org(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> list[Contact]:
        stmt = select(Contact).where(Contact.organization_id == organization_id)

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                (Contact.name.ilike(pattern))
                | (Contact.email.ilike(pattern))
                | (Contact.phone.ilike(pattern))
                | (Contact.position.ilike(pattern))
            )

        stmt = stmt.offset((page - 1) * limit).limit(limit).order_by(Contact.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_starred(self, db: AsyncSession) -> list[Contact]:
        result = await db.execute(select(Contact).where(Contact.is_starred))
        return list(result.scalars().all())

    async def list_by_company(self, db: AsyncSession, company_id: str) -> list[Contact]:
        result = await db.execute(select(Contact).where(Contact.company_id == company_id))
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, contact_id: str) -> Contact | None:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        return result.scalars().first()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[Contact]:
        result = await db.execute(select(Contact).where(Contact.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Contact:
        contact = Contact(**data)
        db.add(contact)
        return contact

    async def delete(self, db: AsyncSession, contact: Contact) -> None:
        await db.delete(contact)
