from collections.abc import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models import Company, Contact, Deal, Document, Invoice, Lead, Payment, Quote, Ticket
from app.repositories.project_access import project_record_access_filter


class DocumentRepository:
    """Query layer for the Document domain — strictly tenant-isolated."""

    @staticmethod
    def _access_filter(access, target_access=None):
        uploader_filter = record_access_filter(
            access,
            assigned_column=Document.uploaded_by,
            created_column=Document.uploaded_by,
        )
        project_context = (target_access or {}).get("projects", access)
        project_filter = project_record_access_filter(
            project_context, project_id_column=Document.project_id, linked=True
        )
        if uploader_filter is None:
            identity_filter = None
        elif project_filter is None:
            identity_filter = or_(uploader_filter, Document.project_id.is_not(None))
        else:
            identity_filter = or_(uploader_filter, project_filter)
        if target_access is None:
            return identity_filter

        target_specs = (
            (Document.lead_id, Lead, "leads", Lead.assigned_to, Lead.created_by),
            (Document.contact_id, Contact, "contacts", Contact.owner_id, Contact.created_by),
            (Document.company_id, Company, "companies", Company.owner_id, Company.created_by),
            (Document.deal_id, Deal, "deals", Deal.assigned_to, Deal.created_by),
            (Document.quote_id, Quote, "quotes", Quote.created_by, Quote.created_by),
            (Document.invoice_id, Invoice, "invoices", Invoice.created_by, Invoice.created_by),
            (Document.ticket_id, Ticket, "tickets", Ticket.assigned_to, Ticket.created_by),
        )
        target_filters = []
        for document_fk, model, module, assigned, created in target_specs:
            target_filter = record_access_filter(
                target_access[module], assigned_column=assigned, created_column=created
            )
            allowed = select(model.id)
            if target_filter is not None:
                allowed = allowed.where(target_filter)
            target_filters.append(or_(document_fk.is_(None), document_fk.in_(allowed)))

        payment_access = record_access_filter(
            target_access["payments"],
            assigned_column=Invoice.created_by,
            created_column=Invoice.created_by,
        )
        allowed_payments = select(Payment.id).join(Invoice, Invoice.id == Payment.invoice_id)
        if payment_access is not None:
            allowed_payments = allowed_payments.where(payment_access)
        target_filters.append(
            or_(Document.payment_id.is_(None), Document.payment_id.in_(allowed_payments))
        )
        project_target = project_record_access_filter(
            target_access["projects"], project_id_column=Document.project_id, linked=True
        )
        if project_target is not None:
            target_filters.append(or_(Document.project_id.is_(None), project_target))
        return and_(*([identity_filter] if identity_filter is not None else []), *target_filters)

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
        ticket_id: str | None = None,
        project_linked: bool = False,
        access=None,
        target_access=None,
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.organization_id == org_id)
        access_filter = self._access_filter(access, target_access)
        if access_filter is not None:
            stmt = stmt.where(access_filter)
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
            (Document.ticket_id, ticket_id),
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
        ticket_id: str | None = None,
        project_linked: bool = False,
        access=None,
        target_access=None,
    ) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.organization_id == org_id)
        access_filter = self._access_filter(access, target_access)
        if access_filter is not None:
            stmt = stmt.where(access_filter)
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
            (Document.ticket_id, ticket_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        if project_linked and not project_id:
            stmt = stmt.where(Document.project_id.is_not(None))
        return int((await db.execute(stmt)).scalar_one())

    async def list_by_ids(
        self, db: AsyncSession, ids: list[str], org_id: str, access=None, target_access=None
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.id.in_(ids), Document.organization_id == org_id)
        access_filter = self._access_filter(access, target_access)
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_document(
        self,
        db: AsyncSession,
        document_id: str,
        org_id: str,
        access=None,
        target_access=None,
    ) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id, Document.organization_id == org_id
        )
        access_filter = self._access_filter(access, target_access)
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_document(self, db: AsyncSession, *, data: dict) -> Document:
        document = Document(**data)
        db.add(document)
        return document

    async def delete_document(self, db: AsyncSession, document: Document) -> None:
        await db.delete(document)
