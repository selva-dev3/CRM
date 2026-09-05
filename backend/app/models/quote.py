import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    automatic_deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="RESTRICT"), unique=True
    )
    currency: Mapped[str | None] = mapped_column(String(10))
    company_id: Mapped[str | None] = mapped_column(String, ForeignKey("companies.id", ondelete="RESTRICT"))
    contact_id: Mapped[str | None] = mapped_column(String, ForeignKey("contacts.id", ondelete="RESTRICT"))
    quote_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(50), default="Draft", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    delivery_id: Mapped[str | None] = mapped_column(String(36))
    delivery_status: Mapped[str | None] = mapped_column(String(30), index=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    delivery_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    pdf_s3_key: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(
        String, ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    product_name: Mapped[str | None] = mapped_column(String(255))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    discount_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tax_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
