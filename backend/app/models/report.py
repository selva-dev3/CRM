from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), default="csv")
    download_url: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_by: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
