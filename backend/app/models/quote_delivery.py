import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuoteDeliveryAttempt(Base):
    __tablename__ = "quote_delivery_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(
        String, ForeignKey("quotes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delivery_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="brevo", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    provider_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
