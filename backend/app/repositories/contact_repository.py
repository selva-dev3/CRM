from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact, ContactAddress
from app.models.organization import Organization


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
        self,
        db: AsyncSession,
        company_id: str,
        *,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(
                Contact.company_id == company_id,
                Contact.organization_id == organization_id,
            )
            .order_by(Contact.created_at.desc(), Contact.id.desc())
        )
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_company(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Contact)
            .where(
                Contact.company_id == company_id,
                Contact.organization_id == organization_id,
            )
        )
        return int((await db.execute(stmt)).scalar_one())

    async def get_by_id(self, db: AsyncSession, contact_id: str) -> Contact | None:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        return result.scalars().first()

    async def get_by_id_scoped(
        self,
        db: AsyncSession,
        *,
        contact_id: str,
        organization_id: str,
        populate_existing: bool = False,
    ) -> Contact | None:
        query = select(Contact).where(
            Contact.id == contact_id,
            Contact.organization_id == organization_id,
        )
        if populate_existing:
            query = query.execution_options(populate_existing=True)
        result = await db.execute(query)
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

    async def get_address(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> ContactAddress | None:
        result = await db.execute(
            select(ContactAddress)
            .join(Contact, Contact.id == ContactAddress.contact_id)
            .where(
                ContactAddress.contact_id == contact_id,
                Contact.organization_id == organization_id,
            )
            .order_by(ContactAddress.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_address(
        self, db: AsyncSession, *, contact_id: str, data: dict
    ) -> ContactAddress:
        address = ContactAddress(contact_id=contact_id, **data)
        db.add(address)
        return address

    async def lock_organization(self, db: AsyncSession, organization_id: str) -> None:
        await db.scalar(
            select(Organization.id).where(Organization.id == organization_id).with_for_update()
        )

    async def find_duplicate(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        email: str,
        phone: str | None,
        exclude_id: str | None = None,
    ) -> Contact | None:
        conditions = [func.lower(func.trim(Contact.email)) == email]
        if phone:
            conditions.append(func.regexp_replace(Contact.phone, r"\D", "", "g") == phone)
        stmt = select(Contact).where(
            Contact.organization_id == organization_id,
            *conditions[:1],
        )
        if exclude_id:
            stmt = stmt.where(Contact.id != exclude_id)
        duplicate = (await db.execute(stmt.limit(1))).scalars().first()
        if duplicate or not phone:
            return duplicate
        phone_stmt = select(Contact).where(
            Contact.organization_id == organization_id,
            conditions[1],
        )
        if exclude_id:
            phone_stmt = phone_stmt.where(Contact.id != exclude_id)
        return (await db.execute(phone_stmt.limit(1))).scalars().first()
