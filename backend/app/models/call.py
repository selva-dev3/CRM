import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import User


class CallLog(Base):
    __tablename__ = "call_logs"
    __table_args__ = (
        CheckConstraint(
            "call_type IN ('Outbound','Inbound')",
            name="ck_call_logs_call_type",
        ),
        CheckConstraint(
            "disposition IS NULL OR disposition IN ('Completed','No Answer','Busy','Failed','Other')",
            name="ck_call_logs_disposition",
        ),
        CheckConstraint(
            "duration_seconds >= 0 AND duration_seconds <= 86400",
            name="ck_call_logs_duration",
        ),
        UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_call_logs_org_creator_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    lead_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    call_type: Mapped[str] = mapped_column(String(50), default="Outbound")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    subject: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    recording_url: Mapped[str | None] = mapped_column(String(500))
    disposition: Mapped[str | None] = mapped_column(String(100))
    follow_up_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_action: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    idempotency_request_hash: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by_user: Mapped["User | None"] = relationship(foreign_keys=[created_by], lazy="joined")
