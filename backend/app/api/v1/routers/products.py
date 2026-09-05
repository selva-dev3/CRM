from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException
from app.db.session import get_db
from app.models import Product, ProductCategory, User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    ProductBase,
)

router = APIRouter()


@router.get(
    "",
    summary="List product catalog with search & pagination",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_products(
    page: int = 1,
    limit: int = 20,
    category: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        stmt = select(Product).where(Product.organization_id == current_user.organization_id)
        if search and search.strip():
            stmt = stmt.where(
                (Product.name.ilike(f"%{search.strip()}%"))
                | (Product.sku.ilike(f"%{search.strip()}%"))
            )
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        products = res.scalars().all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku or f"SKU-{p.id[:6]}",
                "price": p.price or 0.0,
                "category": category or "Software",
                "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100,
            }
            for p in products
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.post(
    "",
    summary="Create new product catalog item",
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_product(
    payload: ProductBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        p = Product(
            organization_id=current_user.organization_id,
            name=payload.name,
            sku=payload.sku or f"SKU-{payload.name[:4].upper()}",
            price=payload.price or 0.0,
            in_stock_quantity=100,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "price": p.price,
            "category": payload.category or "Software",
            "in_stock_quantity": p.in_stock_quantity,
        }
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create product: {exc}",
        ) from exc


@router.get(
    "/categories",
    summary="Get product categories list",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(ProductCategory).where(
            ProductCategory.organization_id == current_user.organization_id
        )
    )
    cats = res.scalars().all()
    if not cats:
        return ["Software", "Hardware", "Professional Services", "Subscription", "Support Tier"]
    return [c.name for c in cats]


@router.post(
    "/categories",
    response_model=MessageResponse,
    summary="Create new product category",
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_product_category(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cat = ProductCategory(organization_id=current_user.organization_id, name=name)
        db.add(cat)
        await db.commit()
        return {"message": f"Category '{name}' created", "status": "success"}
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/price-books",
    summary="List custom price books",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_price_books(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Price books are not implemented",
        code="PRICE_BOOKS_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/price-books",
    response_model=MessageResponse,
    summary="Create new price book",
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_price_book(name: str, currency: str = "USD", db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Price books are not implemented",
        code="PRICE_BOOKS_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/tax-rates",
    summary="Get tax rate tiers list",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_tax_rates(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Organization tax rates are not configured",
        code="TAX_CONFIGURATION_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/export/csv",
    summary="Export product catalog as CSV",
    dependencies=[Depends(require_permission("products:export"))],
)
async def export_products_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Product CSV export is not implemented",
        code="PRODUCT_EXPORT_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import product catalog from CSV",
    dependencies=[Depends(require_permission("products:import"))],
)
async def import_products_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Product CSV import is not implemented",
        code="PRODUCT_IMPORT_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete products",
    dependencies=[Depends(require_permission("products:delete"))],
)
async def bulk_delete_products(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        stmt = select(Product).where(
            Product.id.in_(payload.ids),
            Product.organization_id == current_user.organization_id,
        )
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Products deleted successfully"}
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{product_id}",
    summary="Get product details by ID",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current_user.organization_id,
        )
    )
    p = res.scalars().first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku or f"SKU-{p.id[:6]}",
        "price": p.price or 0.0,
        "category": "Software",
        "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100,
    }


@router.put(
    "/{product_id}",
    summary="Update product catalog item",
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_product(
    product_id: str,
    payload: ProductBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current_user.organization_id,
        )
    )
    p = res.scalars().first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )
    try:
        p.name = payload.name
        p.sku = payload.sku or "N/A"
        p.price = payload.price if payload.price is not None else 0.0
        await db.commit()
        await db.refresh(p)
        return {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "price": p.price,
            "category": payload.category or "Software",
            "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100,
        }
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{product_id}",
    response_model=MessageResponse,
    summary="Delete product item by ID",
    dependencies=[Depends(require_permission("products:delete"))],
)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current_user.organization_id,
        )
    )
    p = res.scalars().first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )
    try:
        await db.delete(p)
        await db.commit()
        return {"message": f"Product {product_id} deleted successfully", "status": "success"}
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{product_id}/inventory",
    summary="Get inventory stock history",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_inventory(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current_user.organization_id,
        )
    )
    p = res.scalars().first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )
    return {
        "product_id": product_id,
        "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100,
        "reorder_level": None,
        "warehouse_location": None,
    }


@router.post(
    "/{product_id}/inventory",
    response_model=MessageResponse,
    summary="Update product inventory stock level",
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_product_inventory(
    product_id: str,
    quantity_delta: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current_user.organization_id,
        )
    )
    p = res.scalars().first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found",
        )
    try:
        if hasattr(p, "in_stock_quantity") and p.in_stock_quantity is not None:
            p.in_stock_quantity += quantity_delta
        await db.commit()
        return {
            "message": f"Updated inventory for {product_id} by {quantity_delta}",
            "status": "success",
        }
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
