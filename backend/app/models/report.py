import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), default="csv")
    download_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    requested_by: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomReport(Base):
    __tablename__ = "custom_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[str | None] = mapped_column(Text)
    metrics_included: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(50), default="Weekly")
    next_run: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    # Delivery claim marker used by the scheduler sweep. While set and in the
    # future exactly one worker owns this row; NULL or stale (past) values mean
    # the schedule is claimable again (crash recovery). See workers/tasks.py.
    claimed_until: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
