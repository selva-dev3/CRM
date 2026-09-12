from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


class DocumentRepository:
    """Query layer for the Document domain — strictly tenant-isolated."""

    async def list_documents(
        self,
        db: AsyncSession,
        *,
        org_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        quote_id: str | None = None,
        invoice_id: str | None = None,
        payment_id: str | None = None,
        project_id: str | None = None,
        project_linked: bool = False,
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.organization_id == org_id)
        if search and search.strip():
            stmt = stmt.where(Document.filename.ilike(f"%{search.strip()}%"))
        for column, value in (
            (Document.lead_id, lead_id),
            (Document.contact_id, contact_id),
            (Document.company_id, company_id),
            (Document.deal_id, deal_id),
            (Document.quote_id, quote_id),
            (Document.invoice_id, invoice_id),
            (Document.payment_id, payment_id),
            (Document.project_id, project_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        if project_linked and not project_id:
            stmt = stmt.where(Document.project_id.is_not(None))
        stmt = (
            stmt.order_by(Document.uploaded_at.desc(), Document.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_documents(
        self,
        db: AsyncSession,
        *,
        org_id: str,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        quote_id: str | None = None,
        invoice_id: str | None = None,
        payment_id: str | None = None,
        project_id: str | None = None,
        project_linked: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.organization_id == org_id)
        if search and search.strip():
            stmt = stmt.where(Document.filename.ilike(f"%{search.strip()}%"))
        for column, value in (
            (Document.lead_id, lead_id),
            (Document.contact_id, contact_id),
            (Document.company_id, company_id),
            (Document.deal_id, deal_id),
            (Document.quote_id, quote_id),
            (Document.invoice_id, invoice_id),
            (Document.payment_id, payment_id),
            (Document.project_id, project_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        if project_linked and not project_id:
            stmt = stmt.where(Document.project_id.is_not(None))
        return int((await db.execute(stmt)).scalar_one())

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], org_id: str
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.id.in_(ids), Document.organization_id == org_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_document(
        self, db: AsyncSession, document_id: str, org_id: str
    ) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id, Document.organization_id == org_id
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_document(self, db: AsyncSession, *, data: dict) -> Document:
        document = Document(**data)
        db.add(document)
        return document

    async def delete_document(self, db: AsyncSession, document: Document) -> None:
        await db.delete(document)
