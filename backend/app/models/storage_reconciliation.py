import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorageReconciliation(Base):
    """Durable findings from the tenant-scoped object-storage reconciler."""

    __tablename__ = "storage_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "object_key", "finding", name="uq_storage_reconciliation"
        ),
        Index("ix_storage_reconciliations_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    finding: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="detected")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
