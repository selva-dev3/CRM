from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str] = mapped_column(String, ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    call_type: Mapped[str] = mapped_column(String(50), default="Outbound")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    recording_url: Mapped[Optional[str]] = mapped_column(String(500))
    disposition: Mapped[Optional[str]] = mapped_column(String(100))
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
