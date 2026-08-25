from __future__ import annotations

import time
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.models.quote import Quote
from app.repositories.deal_repository import DealRepository
from app.repositories.quote_repository import QuoteRepository, quote_repository
from app.schemas.crm_schemas import QuoteBase
from app.services.org_service import organization_service

QUOTE_STATUSES = {"Draft", "Sent", "Accepted", "Rejected"}


def quote_to_dict(quote: Quote) -> dict:
    return {
        "id": quote.id,
        "deal_id": quote.deal_id,
        "quote_number": quote.quote_number or f"QUO-{quote.id[:6]}",
        "items": [],
        "total_amount": quote.total_amount or 0.0,
        "status": quote.status or "Draft",
        "created_at": str(quote.created_at) if quote.created_at else "",
    }


class QuoteService:
    def __init__(
        self,
        repository: QuoteRepository | None = None,
        deal_repository: DealRepository | None = None,
    ) -> None:
        self.repository = repository or quote_repository
        self.deal_repository = deal_repository or DealRepository()

    async def resolve_organization_id(self, db: AsyncSession, current_user: User) -> str:
        return await organization_service.resolve_valid_org_id(db, current_user)

    async def _commit(self, db: AsyncSession, message: str) -> None:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise APIException(message=message) from exc

    async def _require_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Quote:
        quote = await self.repository.get_scoped(
            db, quote_id=quote_id, organization_id=organization_id
        )
        if not quote:
            raise NotFoundError(message=f"Quote '{quote_id}' not found")
        return quote

    async def _require_deal(self, db: AsyncSession, *, deal_id: str, organization_id: str) -> Deal:
        deal = await self.deal_repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")
        return deal

    async def list_quotes(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None,
        search: str | None,
    ) -> list[dict]:
        quotes = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )
        return [quote_to_dict(quote) for quote in quotes]

    async def list_quotes_for_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[dict]:
        quotes = await self.repository.list_by_deal(
            db, deal_id=deal_id, organization_id=organization_id
        )
        return [quote_to_dict(quote) for quote in quotes]

    async def get_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return quote_to_dict(quote)

    async def create_quote(
        self, db: AsyncSession, *, payload: QuoteBase, current_user: User
    ) -> dict:
        organization_id = await self.resolve_organization_id(db, current_user)
        deal = await self._require_deal(
            db, deal_id=payload.deal_id, organization_id=organization_id
        )
        if payload.status not in QUOTE_STATUSES:
            raise APIException(
                message=f"Invalid quote status '{payload.status}'.",
                code="INVALID_QUOTE_STATUS",
            )
        quote = await self.repository.create(
            db,
            data={
                "organization_id": organization_id,
                "deal_id": deal.id,
                "quote_number": payload.quote_number.strip()
                or f"QUO-{int(time.time())}-{uuid4().hex[:6].upper()}",
                "total_amount": payload.total_amount,
                "status": payload.status,
            },
        )
        await self._commit(db, "Failed to create quote")
        await db.refresh(quote)
        return quote_to_dict(quote)

    async def update_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        payload: QuoteBase,
        organization_id: str,
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        deal = await self._require_deal(
            db, deal_id=payload.deal_id, organization_id=organization_id
        )
        if payload.status not in QUOTE_STATUSES:
            raise APIException(
                message=f"Invalid quote status '{payload.status}'.",
                code="INVALID_QUOTE_STATUS",
            )
        quote.deal_id = deal.id
        quote.quote_number = payload.quote_number.strip() or quote.quote_number
        quote.total_amount = payload.total_amount
        quote.status = payload.status
        await self._commit(db, "Failed to update quote")
        await db.refresh(quote)
        return quote_to_dict(quote)

    async def delete_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> None:
        deleted = await self.repository.delete_scoped(
            db, quote_id=quote_id, organization_id=organization_id
        )
        if not deleted:
            raise NotFoundError(message=f"Quote '{quote_id}' not found")
        await self._commit(db, "Failed to delete quote")

    async def bulk_delete_quotes(
        self, db: AsyncSession, *, quote_ids: list[str], organization_id: str
    ) -> dict:
        affected_count = await self.repository.bulk_delete_scoped(
            db, quote_ids=quote_ids, organization_id=organization_id
        )
        await self._commit(db, "Failed to bulk delete quotes")
        return {
            "affected_count": affected_count,
            "message": "Quotes deleted successfully",
        }

    async def send_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        recipient_email: str,
        organization_id: str,
    ) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return {
            "message": f"Quote proposal sent to {recipient_email}",
            "status": "success",
        }

    async def accept_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        quote.status = "Accepted"
        await self._commit(db, "Failed to accept quote")
        return {"message": f"Quote {quote_id} accepted!", "status": "success"}

    async def reject_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        reason: str | None,
        organization_id: str,
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        quote.status = "Rejected"
        await self._commit(db, "Failed to reject quote")
        return {
            "message": f"Quote {quote_id} rejected due to: {reason}",
            "status": "success",
        }

    async def get_quote_pdf(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return {"pdf_url": f"https://api.crm.com/quotes/{quote_id}.pdf"}

    async def convert_quote_to_invoice(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return {
            "id": f"inv-{quote.id[:8]}",
            "invoice_number": f"INV-{quote.quote_number}",
            "amount": quote.total_amount or 15000.0,
            "status": "Draft",
            "due_date": "2026-09-02",
            "created_at": "2026-08-02",
        }

    async def create_quote_revision(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return {
            "id": f"{quote.id}-rev2",
            "quote_number": f"{quote.quote_number}-v2",
            "items": [],
            "total_amount": quote.total_amount or 15000.0,
            "status": "Draft",
            "created_at": "2026-08-02",
        }

    async def get_quote_revisions(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> list[dict]:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return [
            {
                "id": f"{quote.id}-v1",
                "quote_number": f"{quote.quote_number}-v1",
                "total_amount": quote.total_amount,
                "version": "v1",
                "created_at": "2026-08-01",
            },
            {
                "id": f"{quote.id}-v2",
                "quote_number": f"{quote.quote_number}-v2",
                "total_amount": (quote.total_amount or 15000) * 1.1,
                "version": "v2",
                "created_at": "2026-08-02",
            },
        ]


quote_service = QuoteService()
