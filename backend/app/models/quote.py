from sqlalchemy import String, DateTime, Float, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deals.id", ondelete="SET NULL"), index=True)
    quote_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="Draft", index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id: Mapped[str] = mapped_column(String, ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
