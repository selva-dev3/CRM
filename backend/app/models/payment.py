import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "amount > 0 AND amount <= 999999999999.99", name="ck_payments_positive_amount"
        ),
        CheckConstraint(
            "payment_type IN ('Cash','Bank Transfer','UPI','Cheque','Card','Other','Legacy')",
            name="ck_payments_type",
        ),
        UniqueConstraint("organization_id", "payment_number", name="uq_payments_org_number"),
        UniqueConstraint(
            "organization_id",
            "invoice_id",
            "idempotency_key",
            name="uq_payment_invoice_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    invoice_id: Mapped[str] = mapped_column(
        String, ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )
    payment_number: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    recorded_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    legacy_provider_data: Mapped[dict | None] = mapped_column(JSON)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(100))
    receipt_s3_key: Mapped[str | None] = mapped_column(String(500))
    receipt_delivery_status: Mapped[str | None] = mapped_column(String(30), index=True)
    receipt_delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    receipt_delivery_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_provider_message_id: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
