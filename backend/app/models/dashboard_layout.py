import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_dashboard_layouts_org_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    owner_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    widgets: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
