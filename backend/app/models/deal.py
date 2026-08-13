from sqlalchemy import String, Boolean, DateTime, Float, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.db.base import Base

class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage: Mapped[str] = mapped_column(String(100), default="Prospecting", index=True)
    probability: Mapped[float] = mapped_column(Float, default=50.0)
    expected_close_date: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("contacts.id", ondelete="SET NULL"))
    company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("companies.id", ondelete="SET NULL"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class DealStage(Base):
    __tablename__ = "deal_stages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_probability: Mapped[float] = mapped_column(Float, default=50.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

class DealActivity(Base):
    __tablename__ = "deal_activities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String, ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"))
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DealProduct(Base):
    __tablename__ = "deal_products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String, ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
