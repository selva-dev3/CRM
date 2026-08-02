from sqlalchemy import String, Boolean, DateTime, Integer, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    plan: Mapped[str] = mapped_column(String(100), default="Enterprise")
    max_users: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class OrganizationSetting(Base):
    __tablename__ = "organization_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    primary_color: Mapped[str] = mapped_column(String(50), default="#3B82F6")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    language: Mapped[str] = mapped_column(String(10), default="en")

class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active")
    current_period_start: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True))
