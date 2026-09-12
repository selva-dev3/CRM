import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    folder_id: Mapped[str | None] = mapped_column(String, index=True)
    lead_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    quote_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quotes.id", ondelete="SET NULL"), index=True
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("invoices.id", ondelete="SET NULL"), index=True
    )
    payment_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("payments.id", ondelete="SET NULL"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    uploaded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
