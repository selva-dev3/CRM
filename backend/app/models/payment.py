import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id", name="uq_payment_provider_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    invoice_id: Mapped[str] = mapped_column(
        String, ForeignKey("invoices.id", ondelete="RESTRICT"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    checkout_session_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    payment_method: Mapped[str | None] = mapped_column(String(100))
    receipt_s3_key: Mapped[str | None] = mapped_column(String(500))
    receipt_delivery_status: Mapped[str | None] = mapped_column(String(30), index=True)
    receipt_delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    receipt_delivery_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_provider_message_id: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
