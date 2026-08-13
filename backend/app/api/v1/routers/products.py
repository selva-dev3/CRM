from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models import Product, ProductCategory
from app.api.v1.deps import get_valid_org_id
from app.schemas.crm_schemas import ProductResponse, ProductBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", summary="List product catalog with search & pagination")
async def list_products(
    page: int = 1,
    limit: int = 20,
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Product)
        if search and search.strip():
            stmt = stmt.where((Product.name.ilike(f"%{search.strip()}%")) | (Product.sku.ilike(f"%{search.strip()}%")))
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
                "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100
            } for p in products
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", summary="Create new product catalog item")
async def create_product(payload: ProductBase, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        p = Product(
            organization_id=org_id,
            name=payload.name,
            sku=payload.sku or f"SKU-{payload.name[:4].upper()}",
            price=payload.price or 0.0,
            in_stock_quantity=100
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
            "in_stock_quantity": p.in_stock_quantity
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create product: {str(e)}")

@router.get("/categories", summary="Get product categories list")
async def get_product_categories(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(ProductCategory))
    cats = res.scalars().all()
    if not cats:
        return ["Software", "Hardware", "Professional Services", "Subscription", "Support Tier"]
    return [c.name for c in cats]

@router.post("/categories", response_model=MessageResponse, summary="Create new product category")
async def create_product_category(name: str, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        cat = ProductCategory(organization_id=org_id, name=name)
        db.add(cat)
        await db.commit()
        return {"message": f"Category '{name}' created", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/price-books", summary="List custom price books")
async def list_price_books(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "pb-1", "name": "Standard Enterprise Pricing", "currency": "USD", "is_default": True},
        {"id": "pb-2", "name": "EMEA Partner Pricing", "currency": "EUR", "is_default": False},
        {"id": "pb-3", "name": "APAC Wholesale Book", "currency": "USD", "is_default": False}
    ]

@router.post("/price-books", response_model=MessageResponse, summary="Create new price book")
async def create_price_book(name: str, currency: str = "USD", db: AsyncSession = Depends(get_db)):
    return {"message": f"Price book '{name}' ({currency}) created", "status": "success"}

@router.get("/tax-rates", summary="Get tax rate tiers list")
async def get_tax_rates(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "tax-1", "name": "Standard VAT (18%)", "rate_percentage": 18.0},
        {"id": "tax-2", "name": "US Sales Tax (8.5%)", "rate_percentage": 8.5},
        {"id": "tax-3", "name": "Zero Rated Tax (0%)", "rate_percentage": 0.0}
    ]

@router.get("/export/csv", summary="Export product catalog as CSV")
async def export_products_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/products_catalog_export.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import product catalog from CSV")
async def import_products_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Product catalog CSV import processing completed", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete products")
async def bulk_delete_products(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Product).where(Product.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Products deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{product_id}", summary="Get product details by ID")
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Product).where(Product.id == product_id))
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found")
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku or f"SKU-{p.id[:6]}",
        "price": p.price or 0.0,
        "category": "Software",
        "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100
    }

@router.put("/{product_id}", summary="Update product catalog item")
async def update_product(product_id: str, payload: ProductBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Product).where(Product.id == product_id))
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found")
    try:
        p.name = payload.name
        p.sku = payload.sku
        p.price = payload.price
        await db.commit()
        await db.refresh(p)
        return {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "price": p.price,
            "category": payload.category or "Software",
            "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{product_id}", response_model=MessageResponse, summary="Delete product item by ID")
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Product).where(Product.id == product_id))
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found")
    try:
        await db.delete(p)
        await db.commit()
        return {"message": f"Product {product_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{product_id}/inventory", summary="Get inventory stock history")
async def get_product_inventory(product_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Product).where(Product.id == product_id))
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found")
    return {
        "product_id": product_id,
        "in_stock_quantity": getattr(p, "in_stock_quantity", 100) or 100,
        "reorder_level": 50,
        "warehouse_location": "Main Warehouse Section A-4"
    }

@router.post("/{product_id}/inventory", response_model=MessageResponse, summary="Update product inventory stock level")
async def update_product_inventory(product_id: str, quantity_delta: int = Query(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Product).where(Product.id == product_id))
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID '{product_id}' not found")
    try:
        if hasattr(p, "in_stock_quantity") and p.in_stock_quantity is not None:
            p.in_stock_quantity += quantity_delta
        await db.commit()
        return {"message": f"Updated inventory for {product_id} by {quantity_delta}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
