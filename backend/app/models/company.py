from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.db.base import Base

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    website: Mapped[Optional[str]] = mapped_column(String(255))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    parent_company_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("companies.id", ondelete="SET NULL"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String, ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str] = mapped_column(String, ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    role_in_company: Mapped[Optional[str]] = mapped_column(String(100))
