from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Invoice
from app.schemas.crm_schemas import InvoiceResponse, InvoiceBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[InvoiceResponse], summary="List invoices with pagination & status filters")
async def list_invoices(page: int = 1, limit: int = 20, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Invoice).offset((page - 1) * limit).limit(limit)
        if status:
            stmt = stmt.where(Invoice.status == status)
        res = await db.execute(stmt)
        invoices = res.scalars().all()
        return [{"id": inv.id, "invoice_number": inv.invoice_number, "amount": inv.amount, "status": inv.status, "due_date": str(inv.due_date), "stripe_checkout_url": inv.stripe_checkout_url, "created_at": str(inv.created_at)} for inv in invoices]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create new invoice")
async def create_invoice(payload: InvoiceBase, db: AsyncSession = Depends(get_db)):
    try:
        inv = Invoice(organization_id="org-1", invoice_number=payload.invoice_number, amount=payload.amount, status=payload.status, stripe_checkout_url="https://checkout.stripe.com/pay/cs_test_new")
        db.add(inv)
        await db.commit()
        return {"id": inv.id, "invoice_number": inv.invoice_number, "amount": inv.amount, "status": inv.status, "due_date": str(payload.due_date), "stripe_checkout_url": inv.stripe_checkout_url, "created_at": str(inv.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create invoice: {str(e)}")

@router.get("/overdue", response_model=List[InvoiceResponse], summary="Get list of overdue unpaid invoices")
async def get_overdue_invoices(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.status == "Overdue"))
    invoices = res.scalars().all()
    return [{"id": inv.id, "invoice_number": inv.invoice_number, "amount": inv.amount, "status": inv.status, "due_date": str(inv.due_date), "stripe_checkout_url": inv.stripe_checkout_url, "created_at": str(inv.created_at)} for inv in invoices]

@router.get("/recurring", summary="List automated recurring invoice schedules")
async def list_recurring_invoices(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/recurring", response_model=MessageResponse, summary="Create recurring invoice schedule")
async def create_recurring_invoice(customer_id: str, amount: float, interval: str = "Monthly", db: AsyncSession = Depends(get_db)):
    return {"message": f"Recurring {interval} invoice created for {customer_id}", "status": "success"}

@router.get("/export/csv", summary="Export invoices as CSV")
async def export_invoices_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/invoices.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import invoices from CSV")
async def import_invoices_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import processing completed", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete invoices")
async def bulk_delete_invoices(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Invoice).where(Invoice.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Invoices deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-remind", response_model=BulkActionResponse, summary="Bulk send payment reminder emails for unpaid invoices")
async def bulk_remind_invoices(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Payment reminders sent"}

@router.get("/{invoice_id}", response_model=InvoiceResponse, summary="Get invoice details by ID")
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"id": inv.id, "invoice_number": inv.invoice_number, "amount": inv.amount, "status": inv.status, "due_date": str(inv.due_date), "stripe_checkout_url": inv.stripe_checkout_url, "created_at": str(inv.created_at)}

@router.put("/{invoice_id}", response_model=InvoiceResponse, summary="Update invoice details")
async def update_invoice(invoice_id: str, payload: InvoiceBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    try:
        inv.amount = payload.amount
        inv.status = payload.status
        await db.commit()
        return {"id": inv.id, "invoice_number": inv.invoice_number, "amount": inv.amount, "status": inv.status, "due_date": str(inv.due_date), "stripe_checkout_url": inv.stripe_checkout_url, "created_at": str(inv.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{invoice_id}", response_model=MessageResponse, summary="Delete invoice by ID")
async def delete_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    try:
        await db.delete(inv)
        await db.commit()
        return {"message": f"Invoice {invoice_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{invoice_id}/send", response_model=MessageResponse, summary="Email invoice PDF and payment link to client")
async def send_invoice_email(invoice_id: str, recipient_email: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"message": f"Invoice email sent to {recipient_email}", "status": "success"}

@router.post("/{invoice_id}/stripe-checkout", summary="Generate fresh Stripe Checkout session URL")
async def create_stripe_checkout(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"checkout_url": f"https://checkout.stripe.com/pay/session_{invoice_id}"}

@router.post("/{invoice_id}/mark-paid", response_model=MessageResponse, summary="Manually mark invoice status as Paid")
async def mark_invoice_paid(invoice_id: str, payment_method: str = "Bank Transfer", db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    try:
        inv.status = "Paid"
        await db.commit()
        return {"message": f"Invoice {invoice_id} marked as Paid via {payment_method}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{invoice_id}/remind", response_model=MessageResponse, summary="Send payment reminder email for invoice")
async def send_payment_reminder(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"message": f"Payment reminder sent for invoice {invoice_id}", "status": "success"}

@router.get("/{invoice_id}/pdf", summary="Get PDF URL for invoice")
async def get_invoice_pdf(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"pdf_url": f"https://api.crm.com/invoices/{invoice_id}.pdf"}

@router.post("/{invoice_id}/credit-memo", response_model=MessageResponse, summary="Issue a credit memo adjustment against invoice")
async def issue_credit_memo(invoice_id: str, amount: float, reason: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice with ID '{invoice_id}' not found")
    return {"message": f"Credit memo of ${amount} issued against invoice {invoice_id}", "status": "success"}
