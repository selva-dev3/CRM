from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, InvoiceItem
from app.models.audit import AuditLog
from app.models.contact import Contact, ContactAddress
from app.models.deal import Deal, DealActivity, DealProduct
from app.models.organization import Organization
from app.models.product import Product


class InvoiceRepository:
    """DB query layer for the Invoice domain. All queries are organization-scoped."""

    async def get_by_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(
                Invoice.quote_id == quote_id,
                Invoice.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def lock_numbering(self, db: AsyncSession, organization_id: str) -> Organization | None:
        result = await db.execute(
            select(Organization)
            .where(
                Organization.id == organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def advance_numbering(self, db: AsyncSession, organization: Organization) -> int:
        organization.invoice_sequence += 1
        return organization.invoice_sequence

    async def get_billing_address(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> ContactAddress | None:
        result = await db.execute(
            select(ContactAddress)
            .join(Contact, Contact.id == ContactAddress.contact_id)
            .where(
                ContactAddress.contact_id == contact_id,
                Contact.organization_id == organization_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def record_creation(self, db: AsyncSession, invoice: Invoice) -> None:
        if invoice.deal_id:
            db.add(
                DealActivity(
                    deal_id=invoice.deal_id,
                    action=f"Invoice {invoice.invoice_number} created automatically",
                )
            )
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="invoice.auto_created",
                details=invoice.id,
            )
        )

    async def get_scoped(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id, Invoice.organization_id == organization_id
            )
        )
        return result.scalars().first()

    async def list_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Invoice]:
        stmt = select(Invoice).where(Invoice.organization_id == organization_id)
        if status and status.strip():
            stmt = stmt.where(Invoice.status == status.strip())
        if search and search.strip():
            stmt = stmt.where(Invoice.invoice_number.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Invoice.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_deal(self, db: AsyncSession, deal_id: str) -> Invoice | None:
        result = await db.execute(select(Invoice).where(Invoice.deal_id == deal_id))
        return result.scalars().first()

    async def get_by_deal_scoped(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(
                Invoice.deal_id == deal_id,
                Invoice.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> Invoice:
        invoice = Invoice(**data)
        db.add(invoice)
        return invoice

    async def add_items(self, db: AsyncSession, *, items: list[dict]) -> list[InvoiceItem]:
        rows = [InvoiceItem(**item) for item in items]
        db.add_all(rows)
        return rows

    async def list_items(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> list[InvoiceItem]:
        result = await db.execute(
            select(InvoiceItem)
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .where(
                InvoiceItem.invoice_id == invoice_id,
                Invoice.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def queue_delivery(
        self,
        db: AsyncSession,
        invoice: Invoice,
        *,
        delivery_id: str,
        recipient_email: str,
    ) -> None:
        invoice.delivery_id = delivery_id
        invoice.recipient_email = recipient_email
        invoice.delivery_status = "Pending"

    async def claim_delivery(self, db: AsyncSession, now: datetime) -> Invoice | None:
        result = await db.execute(
            select(Invoice)
            .where(Invoice.delivery_status == "Pending", Invoice.delivery_attempts < 3)
            .order_by(Invoice.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        invoice = result.scalar_one_or_none()
        if invoice:
            invoice.delivery_status = "Processing"
            invoice.delivery_claimed_at = now
            invoice.delivery_attempts += 1
        return invoice

    async def expire_delivery_claims(self, db: AsyncSession, now: datetime) -> None:
        result = await db.execute(
            select(Invoice)
            .where(
                Invoice.delivery_status == "Processing",
                Invoice.delivery_claimed_at < now - timedelta(minutes=10),
            )
            .with_for_update(skip_locked=True)
        )
        for invoice in result.scalars():
            invoice.delivery_status = "Unknown"

    async def delivery_result(
        self,
        db: AsyncSession,
        invoice: Invoice,
        *,
        state: str,
        pdf_key: str | None = None,
        message_id: str | None = None,
        at: datetime | None = None,
    ) -> None:
        invoice.delivery_status = state
        if pdf_key:
            invoice.pdf_s3_key = pdf_key
        if message_id:
            invoice.provider_message_id = message_id
            invoice.sent_at = at or datetime.now(UTC)
            if invoice.deal_id:
                db.add(
                    DealActivity(
                        deal_id=invoice.deal_id,
                        action=f"Invoice {invoice.invoice_number} sent to customer",
                    )
                )
            db.add(
                AuditLog(
                    organization_id=invoice.organization_id,
                    action="invoice.sent",
                    details=invoice.id,
                )
            )

    async def record_reminder(self, db: AsyncSession, invoice: Invoice, at: datetime) -> None:
        invoice.reminder_count += 1
        invoice.last_reminded_at = at
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="invoice.reminder_sent",
                details=invoice.id,
            )
        )

    async def list_due_reminder_candidates(
        self, db: AsyncSession, *, now: datetime, limit: int = 20
    ) -> list[tuple[str, str]]:
        result = await db.execute(
            select(Invoice.id, Invoice.organization_id)
            .where(
                Invoice.status.in_(("Pending", "Overdue")),
                Invoice.paid_amount == 0,
                Invoice.delivery_status == "Sent",
                Invoice.due_date <= now + timedelta(days=3),
                Invoice.reminder_count < 3,
                or_(
                    Invoice.last_reminded_at.is_(None),
                    Invoice.last_reminded_at <= now - timedelta(hours=24),
                ),
            )
            .order_by(Invoice.due_date, Invoice.created_at)
            .limit(limit)
        )
        return [(row.id, row.organization_id) for row in result]

    async def delete(self, db: AsyncSession, invoice: Invoice) -> None:
        await db.delete(invoice)

    # --- deal / product lookups used by the conversion flow ---

    async def get_deal_scoped(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> Deal | None:
        result = await db.execute(
            select(Deal).where(Deal.id == deal_id, Deal.organization_id == organization_id)
        )
        return result.scalars().first()

    async def list_deal_products(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[DealProduct]:
        result = await db.execute(
            select(DealProduct)
            .join(Deal, Deal.id == DealProduct.deal_id)
            .where(
                DealProduct.deal_id == deal_id,
                Deal.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def get_product_scoped(
        self, db: AsyncSession, *, product_id: str, organization_id: str
    ) -> Product | None:
        result = await db.execute(
            select(Product).where(
                Product.id == product_id, Product.organization_id == organization_id
            )
        )
        return result.scalars().first()


invoice_repository = InvoiceRepository()
