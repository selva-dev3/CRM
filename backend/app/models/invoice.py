from sqlalchemy import String, DateTime, Float, Integer, Text, ForeignKey, func, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.db.base import Base

class Invoice(Base):
    __tablename__ = "invoices"
    # Business rule: a standard one-time sale yields at most one invoice per deal.
    __table_args__ = (
        Index(
            "uq_invoices_one_per_deal",
            "deal_id",
            unique=True,
            postgresql_where=text("deal_id IS NOT NULL"),
            sqlite_where=text("deal_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    quote_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("quotes.id", ondelete="SET NULL"))
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deals.id", ondelete="SET NULL"), index=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("companies.id", ondelete="SET NULL"))
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contacts.id", ondelete="SET NULL"))
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    discount_total: Mapped[float] = mapped_column(Float, default=0.0)
    tax_total: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="Draft", index=True)
    due_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))
    stripe_checkout_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(String, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    tax_percent: Mapped[float] = mapped_column(Float, default=0.0)
