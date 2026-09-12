from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import SalesOrder, SalesOrderItem, User
from app.models.quote import Quote
from app.repositories.order_repository import OrderRepository, order_repository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.quote_repository import quote_repository as default_quote_repository
from app.services.record_access_service import record_access_service


def order_to_dict(order: SalesOrder, items: list[SalesOrderItem] | None = None) -> dict:
    return {
        "id": order.id,
        "quote_id": order.quote_id,
        "deal_id": order.deal_id,
        "company_id": order.company_id,
        "contact_id": order.contact_id,
        "order_number": order.order_number,
        "status": order.status,
        "currency": order.currency,
        "subtotal": float(order.subtotal),
        "discount_total": float(order.discount_total),
        "tax_total": float(order.tax_total),
        "total": float(order.total),
        "confirmed_at": order.confirmed_at.isoformat(),
        "fulfilled_at": order.fulfilled_at.isoformat() if order.fulfilled_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "discount_percent": float(item.discount_percent),
                "tax_percent": float(item.tax_percent),
                "subtotal": float(item.subtotal),
                "discount_total": float(item.discount_total),
                "tax_total": float(item.tax_total),
                "total": float(item.total),
            }
            for item in (items or [])
        ],
    }


class OrderService:
    def __init__(
        self,
        repository: OrderRepository | None = None,
        quote_repository: QuoteRepository | None = None,
    ) -> None:
        self.repository = repository or order_repository
        self.quote_repository = quote_repository or default_quote_repository

    @staticmethod
    def organization_id(current_user: User) -> str:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="Authenticated organization context is required")
        return organization_id

    async def ensure_from_accepted_quote(self, db: AsyncSession, quote: Quote) -> SalesOrder:
        existing = await self.repository.get_by_quote(
            db, quote_id=quote.id, organization_id=quote.organization_id
        )
        if existing:
            return existing
        if quote.status != "Accepted" or not quote.accepted_at or not quote.approved_at:
            raise ConflictError(message="Only an approved and accepted quote can create an order")
        items = await self.quote_repository.list_items(
            db, quote_id=quote.id, organization_id=quote.organization_id
        )
        if not items or not quote.currency:
            raise ConflictError(message="Accepted quote items and currency are required")
        if any(not item.product_name or item.total is None for item in items):
            raise ConflictError(message="Accepted quote product snapshots are incomplete")
        organization = await self.repository.lock_numbering(db, quote.organization_id)
        if not organization or not organization.order_prefix:
            raise NotFoundError(message="Organization not found")
        organization.order_sequence += 1
        now = datetime.now(UTC)
        total = sum((item.total or Decimal(0) for item in items), Decimal(0))
        if total <= 0 or total != Decimal(str(quote.total_amount)):
            raise ConflictError(message="Accepted quote total is invalid")
        order = SalesOrder(
            organization_id=quote.organization_id,
            quote_id=quote.id,
            deal_id=quote.deal_id,
            company_id=quote.company_id,
            contact_id=quote.contact_id,
            created_by=quote.created_by,
            order_number=f"{organization.order_prefix}-{now.year}-{organization.order_sequence:06d}",
            status="Confirmed",
            currency=quote.currency,
            subtotal=sum((item.subtotal or Decimal(0) for item in items), Decimal(0)),
            discount_total=sum((item.discount_total or Decimal(0) for item in items), Decimal(0)),
            tax_total=sum((item.tax_total or Decimal(0) for item in items), Decimal(0)),
            total=total,
            confirmed_at=now,
        )
        db.add(order)
        await db.flush()
        db.add_all(
            [
                SalesOrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount_percent=item.discount_percent,
                    tax_percent=item.tax_percent,
                    subtotal=item.subtotal or 0,
                    discount_total=item.discount_total or 0,
                    tax_total=item.tax_total or 0,
                    total=item.total or 0,
                )
                for item in items
            ]
        )
        return order

    async def create_from_quote(self, db: AsyncSession, current_user: User, quote_id: str) -> dict:
        organization_id = self.organization_id(current_user)
        access = await record_access_service.resolve(db, current_user, "orders")
        try:
            quote = await self.repository.get_quote(
                db, quote_id=quote_id, organization_id=organization_id, lock=True
            )
            if not quote:
                raise NotFoundError(message="Quote not found")
            order = await self.ensure_from_accepted_quote(db, quote)
            if not record_access_service.allows(
                access, assigned_to=order.created_by, created_by=order.created_by
            ):
                raise NotFoundError(message="Quote not found")
            invoice = await self.repository.get_invoice_for_quote(
                db, quote_id=quote.id, organization_id=organization_id
            )
            if invoice and not invoice.order_id:
                invoice.order_id = order.id
            await db.commit()
            await db.refresh(order)
            items = await self.repository.list_items(
                db, order_id=order.id, organization_id=organization_id
            )
            return order_to_dict(order, items)
        except Exception:
            await db.rollback()
            raise

    async def list(self, db: AsyncSession, current_user: User, **filters) -> list[dict]:
        access = await record_access_service.resolve(db, current_user, "orders")
        orders = await self.repository.list(
            db, organization_id=self.organization_id(current_user), access=access, **filters
        )
        return [order_to_dict(order) for order in orders]

    async def count(self, db: AsyncSession, current_user: User, **filters) -> int:
        access = await record_access_service.resolve(db, current_user, "orders")
        return await self.repository.count(
            db, organization_id=self.organization_id(current_user), access=access, **filters
        )

    async def get(self, db: AsyncSession, current_user: User, order_id: str) -> dict:
        organization_id = self.organization_id(current_user)
        access = await record_access_service.resolve(db, current_user, "orders")
        order = await self.repository.get(
            db, order_id=order_id, organization_id=organization_id, access=access
        )
        if not order:
            raise NotFoundError(message="Order not found")
        items = await self.repository.list_items(
            db, order_id=order_id, organization_id=organization_id
        )
        return order_to_dict(order, items)

    async def update_status(
        self, db: AsyncSession, current_user: User, order_id: str, status: str
    ) -> dict:
        organization_id = self.organization_id(current_user)
        access = await record_access_service.resolve(db, current_user, "orders")
        order = await self.repository.get(
            db,
            order_id=order_id,
            organization_id=organization_id,
            lock=True,
            access=access,
        )
        if not order:
            raise NotFoundError(message="Order not found")
        if order.status != "Confirmed":
            raise ConflictError(message="Only confirmed orders can be updated")
        now = datetime.now(UTC)
        order.status = status
        if status == "Fulfilled":
            order.fulfilled_at = now
        else:
            order.cancelled_at = now
        try:
            await db.commit()
        except SQLAlchemyError as error:
            await db.rollback()
            raise APIException(message="Failed to update order", status_code=400) from error
        await db.refresh(order)
        items = await self.repository.list_items(
            db, order_id=order.id, organization_id=organization_id
        )
        return order_to_dict(order, items)


order_service = OrderService()
