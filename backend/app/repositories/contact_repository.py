from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
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

    async def count_by_org(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Contact)
            .where(Contact.organization_id == organization_id)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                (Contact.name.ilike(pattern))
                | (Contact.email.ilike(pattern))
                | (Contact.phone.ilike(pattern))
                | (Contact.position.ilike(pattern))
            )
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def list_starred(self, db: AsyncSession, *, organization_id: str) -> list[Contact]:
        result = await db.execute(
            select(Contact).where(Contact.is_starred, Contact.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def list_by_company(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list[Contact]:
        result = await db.execute(
            select(Contact).where(
                Contact.company_id == company_id,
                Contact.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, contact_id: str) -> Contact | None:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        return result.scalars().first()

    async def get_by_id_scoped(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> Contact | None:
        result = await db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], *, organization_id: str
    ) -> list[Contact]:
        result = await db.execute(
            select(Contact).where(Contact.id.in_(ids), Contact.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Contact:
        contact = Contact(**data)
        db.add(contact)
        return contact

    async def delete(self, db: AsyncSession, contact: Contact) -> None:
        await db.delete(contact)

    async def company_exists(
        self, db: AsyncSession, *, company_id: str, organization_id: str
    ) -> bool:
        result = await db.execute(
            select(Company.id).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none() is not None
