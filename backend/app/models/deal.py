from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from app.database import Base

class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage: Mapped[str] = mapped_column(String(100), default="Prospecting")
    probability: Mapped[float] = mapped_column(Float, default=50.0)
    assigned_to: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expected_close_date: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
