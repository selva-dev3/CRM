from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import PriceBook, PriceBookEntry, User
from app.repositories.price_book_repository import PriceBookRepository, price_book_repository
from app.schemas.price_book import PriceBookCreate, PriceBookEntryUpsert, PriceBookUpdate


def price_book_to_dict(price_book: PriceBook, product_count: int = 0) -> dict:
    return {
        "id": price_book.id,
        "name": price_book.name,
        "currency": price_book.currency,
        "is_default": price_book.is_default,
        "is_active": price_book.is_active,
        "product_count": product_count,
        "created_at": price_book.created_at.isoformat() if price_book.created_at else None,
        "updated_at": price_book.updated_at.isoformat() if price_book.updated_at else None,
    }


class PriceBookService:
    def __init__(self, repository: PriceBookRepository | None = None) -> None:
        self.repository = repository or price_book_repository

    @staticmethod
    def organization_id(current_user: User) -> str:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="Authenticated organization context is required")
        return organization_id

    async def _commit(self, db: AsyncSession) -> None:
        try:
            await db.commit()
        except IntegrityError as error:
            await db.rollback()
            raise ConflictError(message="A price book with this name already exists") from error
        except SQLAlchemyError as error:
            await db.rollback()
            raise APIException(message="Failed to save price book", status_code=400) from error

    async def list(self, db: AsyncSession, current_user: User) -> list[dict]:
        rows = await self.repository.list(db, organization_id=self.organization_id(current_user))
        return [price_book_to_dict(book, count) for book, count in rows]

    async def context(self, db: AsyncSession, current_user: User) -> dict:
        currency = await self.repository.get_organization_currency(
            db, organization_id=self.organization_id(current_user)
        )
        return {"currency": (currency or "USD").upper()}

    async def create(self, db: AsyncSession, current_user: User, payload: PriceBookCreate) -> dict:
        organization_id = self.organization_id(current_user)
        if payload.is_default:
            await self.repository.unset_default(db, organization_id)
        book = PriceBook(
            organization_id=organization_id,
            name=payload.name.strip(),
            currency=payload.currency,
            is_default=payload.is_default,
        )
        db.add(book)
        await self._commit(db)
        await db.refresh(book)
        return price_book_to_dict(book)

    async def update(
        self,
        db: AsyncSession,
        current_user: User,
        price_book_id: str,
        payload: PriceBookUpdate,
    ) -> dict:
        organization_id = self.organization_id(current_user)
        book = await self.repository.get(
            db, price_book_id=price_book_id, organization_id=organization_id
        )
        if not book:
            raise NotFoundError(message="Price book not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("is_default"):
            await self.repository.unset_default(db, organization_id)
        if "name" in updates:
            updates["name"] = updates["name"].strip()
        for field, value in updates.items():
            setattr(book, field, value)
        await self._commit(db)
        await db.refresh(book)
        return price_book_to_dict(book)

    async def delete(self, db: AsyncSession, current_user: User, price_book_id: str) -> dict:
        book = await self.repository.get(
            db,
            price_book_id=price_book_id,
            organization_id=self.organization_id(current_user),
        )
        if not book:
            raise NotFoundError(message="Price book not found")
        await db.delete(book)
        await self._commit(db)
        return {"message": "Price book deleted", "status": "success"}

    async def entries(self, db: AsyncSession, current_user: User, price_book_id: str) -> list[dict]:
        organization_id = self.organization_id(current_user)
        if not await self.repository.get(
            db, price_book_id=price_book_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Price book not found")
        rows = await self.repository.list_entries(
            db, price_book_id=price_book_id, organization_id=organization_id
        )
        return [
            {
                "id": entry.id,
                "price_book_id": entry.price_book_id,
                "product_id": entry.product_id,
                "product_name": product.name,
                "product_sku": product.sku,
                "unit_price": float(entry.unit_price),
                "is_active": entry.is_active,
            }
            for entry, product in rows
        ]

    async def upsert_entry(
        self,
        db: AsyncSession,
        current_user: User,
        price_book_id: str,
        product_id: str,
        payload: PriceBookEntryUpsert,
    ) -> dict:
        organization_id = self.organization_id(current_user)
        if not await self.repository.get(
            db, price_book_id=price_book_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Price book not found")
        if not await self.repository.get_product(
            db, product_id=product_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Product not found")
        entry = await self.repository.get_entry(
            db, price_book_id=price_book_id, product_id=product_id
        )
        if entry:
            entry.unit_price = payload.unit_price
            entry.is_active = payload.is_active
        else:
            entry = PriceBookEntry(
                price_book_id=price_book_id,
                product_id=product_id,
                unit_price=payload.unit_price,
                is_active=payload.is_active,
            )
            db.add(entry)
        await self._commit(db)
        return {"message": "Price book entry saved", "status": "success"}

    async def delete_entry(
        self,
        db: AsyncSession,
        current_user: User,
        price_book_id: str,
        product_id: str,
    ) -> dict:
        organization_id = self.organization_id(current_user)
        if not await self.repository.get(
            db, price_book_id=price_book_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Price book not found")
        entry = await self.repository.get_entry(
            db, price_book_id=price_book_id, product_id=product_id
        )
        if not entry:
            raise NotFoundError(message="Price book entry not found")
        await db.delete(entry)
        await self._commit(db)
        return {"message": "Price book entry deleted", "status": "success"}


price_book_service = PriceBookService()
