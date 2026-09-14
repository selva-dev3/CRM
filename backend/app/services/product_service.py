from decimal import Decimal
from uuid import uuid4

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import Product, User
from app.repositories.product_repository import ProductRepository, product_repository
from app.schemas.crm_schemas import ProductBase
from app.services.org_service import organization_service

logger = get_logger(__name__)


def product_to_dict(product: Product, category_name: str | None = None) -> dict:
    stock = product.in_stock_quantity
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "price": float(product.price),
        "category": category_name,
        "in_stock_quantity": int(stock) if stock is not None else 0,
    }


class ProductService:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or product_repository

    async def _organization_id(self, db: AsyncSession, user: User) -> str:
        return await organization_service.resolve_valid_org_id(db, user)

    async def _category_id(
        self, db: AsyncSession, *, organization_id: str, name: str | None
    ) -> str | None:
        if not name:
            return None
        category_id = await self.repository.category_id(
            db, organization_id=organization_id, name=name
        )
        if not category_id:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="PRODUCT_CATEGORY_NOT_FOUND",
                message=f"Product category '{name}' does not exist",
            )
        return category_id

    @staticmethod
    def _sku(payload: ProductBase) -> str:
        supplied = (payload.sku or "").strip()
        if supplied and supplied.upper() != "N/A":
            return supplied
        prefix = "".join(character for character in payload.name.upper() if character.isalnum())[:8]
        return f"SKU-{prefix or 'ITEM'}-{uuid4().hex[:8].upper()}"

    @staticmethod
    async def _commit(db: AsyncSession, action: str) -> None:
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(
                message="A product with this SKU already exists in the organization",
                code="PRODUCT_SKU_CONFLICT",
            ) from exc
        except Exception as exc:
            await db.rollback()
            logger.exception("Product %s failed", action)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Unable to {action} product. Please try again later.",
            ) from exc

    async def list_products(
        self, db: AsyncSession, *, user: User, page: int, limit: int,
        search: str | None = None, category: str | None = None,
    ) -> tuple[list[dict], int]:
        organization_id = await self._organization_id(db, user)
        rows = await self.repository.list(
            db, organization_id=organization_id, page=page, limit=limit,
            search=search, category=category,
        )
        total = await self.repository.count(
            db, organization_id=organization_id, search=search, category=category
        )
        return [product_to_dict(product, name) for product, name in rows], total

    async def create_product(
        self, db: AsyncSession, *, payload: ProductBase, user: User
    ) -> dict:
        organization_id = await self._organization_id(db, user)
        try:
            category_id = await self._category_id(
                db, organization_id=organization_id, name=payload.category
            )
            product = await self.repository.create(
                db,
                data={
                    "organization_id": organization_id,
                    "category_id": category_id,
                    "name": payload.name,
                    "sku": self._sku(payload),
                    "price": Decimal(str(payload.price if payload.price is not None else payload.unit_price)),
                    "in_stock_quantity": payload.in_stock_quantity or 0,
                    "is_active": payload.is_active if payload.is_active is not None else True,
                },
            )
            await self._commit(db, "create")
            await db.refresh(product)
            return product_to_dict(product, payload.category)
        except APIException:
            await db.rollback()
            raise

    async def list_categories(self, db: AsyncSession, *, user: User) -> list[str]:
        organization_id = await self._organization_id(db, user)
        return [
            category.name
            for category in await self.repository.list_categories(
                db, organization_id=organization_id
            )
        ]

    async def create_category(self, db: AsyncSession, *, name: str, user: User) -> dict:
        normalized = name.strip()
        if not normalized:
            raise APIException(status_code=422, message="Product category name is required")
        organization_id = await self._organization_id(db, user)
        try:
            await self.repository.create_category(
                db, organization_id=organization_id, name=normalized
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(
                message="A product category with this name already exists",
                code="PRODUCT_CATEGORY_CONFLICT",
            ) from exc
        except Exception as exc:
            await db.rollback()
            logger.exception("Product category creation failed")
            raise APIException(status_code=500, message="Unable to create product category") from exc
        return {"message": f"Category '{normalized}' created", "status": "success"}

    async def get_product(self, db: AsyncSession, *, product_id: str, user: User) -> dict:
        organization_id = await self._organization_id(db, user)
        row = await self.repository.get_with_category(
            db, product_id=product_id, organization_id=organization_id
        )
        if not row:
            raise NotFoundError(message=f"Product with ID '{product_id}' not found")
        return product_to_dict(row[0], row[1])

    async def update_product(
        self, db: AsyncSession, *, product_id: str, payload: ProductBase, user: User
    ) -> dict:
        organization_id = await self._organization_id(db, user)
        product = await self.repository.get(
            db, product_id=product_id, organization_id=organization_id, lock=True
        )
        if not product:
            raise NotFoundError(message=f"Product with ID '{product_id}' not found")
        try:
            product.category_id = await self._category_id(
                db, organization_id=organization_id, name=payload.category
            )
            product.name = payload.name
            supplied_sku = (payload.sku or "").strip()
            if supplied_sku and supplied_sku.upper() != "N/A":
                product.sku = supplied_sku
            product.price = Decimal(str(payload.price if payload.price is not None else 0))
            if payload.in_stock_quantity is not None:
                product.in_stock_quantity = payload.in_stock_quantity
            if payload.is_active is not None:
                product.is_active = payload.is_active
            await self._commit(db, "update")
            await db.refresh(product)
            return product_to_dict(product, payload.category)
        except APIException:
            await db.rollback()
            raise

    async def delete_products(
        self, db: AsyncSession, *, ids: list[str], user: User
    ) -> int:
        organization_id = await self._organization_id(db, user)
        products = await self.repository.list_by_ids(db, ids=ids, organization_id=organization_id)
        try:
            for product in products:
                await self.repository.delete(db, product)
            await self._commit(db, "delete")
            return len(products)
        except APIException:
            raise

    async def delete_product(self, db: AsyncSession, *, product_id: str, user: User) -> None:
        organization_id = await self._organization_id(db, user)
        product = await self.repository.get(
            db, product_id=product_id, organization_id=organization_id, lock=True
        )
        if not product:
            raise NotFoundError(message=f"Product with ID '{product_id}' not found")
        await self.repository.delete(db, product)
        await self._commit(db, "delete")

    async def inventory(self, db: AsyncSession, *, product_id: str, user: User) -> dict:
        organization_id = await self._organization_id(db, user)
        product = await self.repository.get(
            db, product_id=product_id, organization_id=organization_id
        )
        if not product:
            raise NotFoundError(message=f"Product with ID '{product_id}' not found")
        return {
            "product_id": product_id,
            "in_stock_quantity": int(product.in_stock_quantity or 0),
            "reorder_level": None,
            "warehouse_location": None,
        }

    async def adjust_inventory(
        self, db: AsyncSession, *, product_id: str, quantity_delta: int, user: User
    ) -> dict:
        organization_id = await self._organization_id(db, user)
        product = await self.repository.get(
            db, product_id=product_id, organization_id=organization_id, lock=True
        )
        if not product:
            raise NotFoundError(message=f"Product with ID '{product_id}' not found")
        current = int(product.in_stock_quantity or 0)
        if current + quantity_delta < 0:
            await db.rollback()
            raise ConflictError(
                message="Inventory adjustment cannot make stock negative",
                code="INSUFFICIENT_INVENTORY",
            )
        product.in_stock_quantity = current + quantity_delta
        await self._commit(db, "update inventory for")
        return {
            "message": f"Updated inventory for {product_id} by {quantity_delta}",
            "status": "success",
        }


product_service = ProductService()
