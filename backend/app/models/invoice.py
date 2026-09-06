import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    # Business rule: a standard one-time sale yields at most one invoice per deal.
    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft','Finalized','Accepted','Cancelled')", name="ck_invoices_lifecycle"
        ),
        CheckConstraint(
            "payment_status IN ('Pending','Partially Paid','Paid')",
            name="ck_invoices_payment_status",
        ),
        UniqueConstraint("organization_id", "quote_id", name="uq_invoices_org_quote"),
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoices_org_number"),
        Index(
            "uq_invoices_one_per_deal",
            "deal_id",
            unique=True,
            postgresql_where=text("deal_id IS NOT NULL"),
            sqlite_where=text("deal_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quotes.id", ondelete="SET NULL")
    )
    deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL")
    )
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    invoice_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    billing_snapshot: Mapped[dict | None] = mapped_column(JSON)
    payment_status: Mapped[str] = mapped_column(
        String(30), default="Pending", server_default="Pending"
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    public_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legacy_provider_data: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="Draft", index=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_id: Mapped[str | None] = mapped_column(String(36))
    delivery_status: Mapped[str | None] = mapped_column(String(30), index=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    delivery_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    pdf_s3_key: Mapped[str | None] = mapped_column(String(500))
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(
        String, ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Line item", server_default="Line item"
    )
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
