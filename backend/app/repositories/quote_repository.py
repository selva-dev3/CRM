from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, Quote
from app.models.audit import AuditLog
from app.models.deal import DealActivity
from app.models.organization import Organization
from app.models.quote import QuoteItem


class QuoteRepository:
    """Database access for quotes, with explicit organization scoping."""

    async def get_invoice_reference(self, db: AsyncSession, *, quote_id: str, organization_id: str):
        result = await db.execute(
            select(Invoice).where(
                Invoice.quote_id == quote_id, Invoice.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_automatic(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> Quote | None:
        result = await db.execute(
            select(Quote).where(
                Quote.automatic_deal_id == deal_id,
                Quote.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_organization(self, db: AsyncSession, organization_id: str) -> Organization | None:
        result = await db.execute(select(Organization).where(Organization.id == organization_id))
        return result.scalar_one_or_none()

    async def lock_numbering(self, db: AsyncSession, organization_id: str) -> Organization | None:
        result = await db.execute(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def advance_numbering(self, db: AsyncSession, organization: Organization) -> int:
        organization.quote_sequence += 1
        return organization.quote_sequence

    async def add_items(self, db: AsyncSession, items: list[dict]) -> None:
        db.add_all([QuoteItem(**item) for item in items])

    async def list_items(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> list[QuoteItem]:
        result = await db.execute(
            select(QuoteItem)
            .join(Quote)
            .where(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def record_automatic_creation(
        self, db: AsyncSession, quote: Quote, actor_id: str
    ) -> None:
        db.add(
            AuditLog(
                organization_id=quote.organization_id,
                user_id=actor_id,
                action="deal.won",
                details=quote.deal_id,
            )
        )
        db.add(
            AuditLog(
                organization_id=quote.organization_id,
                user_id=actor_id,
                action="quote.auto_created",
                details=quote.id,
            )
        )

    async def lock_scoped(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Quote | None:
        result = await db.execute(
            select(Quote)
            .where(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def lock_public(self, db: AsyncSession, token_hash: str) -> Quote | None:
        result = await db.execute(
            select(Quote)
            .where(Quote.public_token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def approve(
        self, db: AsyncSession, quote: Quote, *, actor_id: str, at, expires_at
    ) -> None:
        quote.status = "Approved"
        quote.approved_at = at
        quote.approved_by = actor_id
        quote.expires_at = expires_at
        if quote.deal_id:
            db.add(
                DealActivity(
                    deal_id=quote.deal_id,
                    action=f"Quote {quote.quote_number} approved",
                    performed_by=actor_id,
                )
            )
        db.add(
            AuditLog(
                organization_id=quote.organization_id,
                user_id=actor_id,
                action="quote.approved",
                details=quote.id,
            )
        )

    async def accept_public(
        self, db: AsyncSession, quote: Quote, *, customer_email: str, at
    ) -> None:
        quote.status = "Accepted"
        quote.accepted_at = at
        quote.accepted_by = customer_email
        if quote.deal_id:
            db.add(
                DealActivity(
                    deal_id=quote.deal_id,
                    action=f"Quote {quote.quote_number} accepted by customer",
                )
            )
        db.add(
            AuditLog(
                organization_id=quote.organization_id, action="quote.accepted", details=quote.id
            )
        )

    async def reject_public(
        self, db: AsyncSession, quote: Quote, *, reason: str | None = None
    ) -> None:
        quote.status = "Rejected"
        quote.rejected_at = datetime.now(UTC)
        quote.rejection_reason = reason
        if quote.deal_id:
            db.add(
                DealActivity(
                    deal_id=quote.deal_id,
                    action=f"Quote {quote.quote_number} rejected by customer",
                )
            )
        db.add(
            AuditLog(
                organization_id=quote.organization_id, action="quote.rejected", details=quote.id
            )
        )

    async def queue_delivery(
        self,
        db: AsyncSession,
        quote: Quote,
        *,
        delivery_id: str,
        recipient_email: str,
        token_hash: str,
    ) -> None:
        quote.delivery_id = delivery_id
        quote.recipient_email = recipient_email
        quote.public_token_hash = token_hash
        quote.delivery_status = "Pending"

    async def claim_delivery(self, db: AsyncSession, now: datetime) -> Quote | None:
        result = await db.execute(
            select(Quote)
            .where(Quote.delivery_status == "Pending", Quote.delivery_attempts < 3)
            .order_by(Quote.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        quote = result.scalar_one_or_none()
        if quote:
            quote.delivery_status = "Processing"
            quote.delivery_claimed_at = now
            quote.delivery_attempts += 1
        return quote

    async def delivery_result(
        self,
        db: AsyncSession,
        quote: Quote,
        *,
        state: str,
        pdf_key: str | None = None,
        message_id: str | None = None,
        at: datetime | None = None,
    ) -> None:
        quote.delivery_status = state
        if pdf_key:
            quote.pdf_s3_key = pdf_key
        if message_id:
            quote.provider_message_id = message_id
            quote.sent_at = at
            quote.status = "Sent"
            if quote.deal_id:
                db.add(
                    DealActivity(
                        deal_id=quote.deal_id,
                        action=f"Quote {quote.quote_number} sent to customer",
                    )
                )
            db.add(
                AuditLog(
                    organization_id=quote.organization_id, action="quote.sent", details=quote.id
                )
            )

    async def expire_delivery_claims(self, db: AsyncSession, now: datetime) -> None:
        result = await db.execute(
            select(Quote)
            .where(
                Quote.delivery_status == "Processing",
                Quote.delivery_claimed_at < now - timedelta(minutes=10),
            )
            .with_for_update(skip_locked=True)
        )
        for quote in result.scalars():
            quote.delivery_status = "Unknown"

    async def list_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Quote]:
        stmt = select(Quote).where(Quote.organization_id == organization_id)
        if status and status.strip():
            stmt = stmt.where(Quote.status == status.strip())
        if search and search.strip():
            stmt = stmt.where(Quote.quote_number.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Quote.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_scoped(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Quote | None:
        result = await db.execute(
            select(Quote).where(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[Quote]:
        result = await db.execute(
            select(Quote)
            .where(
                Quote.deal_id == deal_id,
                Quote.organization_id == organization_id,
            )
            .order_by(Quote.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Quote:
        quote = Quote(**data)
        db.add(quote)
        return quote

    async def delete_scoped(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> bool:
        result = cast(
            CursorResult[Any],
            await db.execute(
                delete(Quote).where(
                    Quote.id == quote_id,
                    Quote.organization_id == organization_id,
                    Quote.automatic_deal_id.is_(None),
                )
            ),
        )
        return bool(result.rowcount)

    async def bulk_delete_scoped(
        self, db: AsyncSession, *, quote_ids: list[str], organization_id: str
    ) -> int:
        if not quote_ids:
            return 0
        result = cast(
            CursorResult[Any],
            await db.execute(
                delete(Quote).where(
                    Quote.id.in_(quote_ids),
                    Quote.organization_id == organization_id,
                    Quote.automatic_deal_id.is_(None),
                )
            ),
        )
        return int(result.rowcount or 0)


quote_repository = QuoteRepository()
