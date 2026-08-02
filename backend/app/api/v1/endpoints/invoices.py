from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import InvoiceResponse, InvoiceBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[InvoiceResponse], summary="List invoices with pagination & status filters")
async def list_invoices(page: int = 1, limit: int = 20, status: Optional[str] = None):
    return [
        {"id": "inv-1", "invoice_number": "INV-2026-001", "amount": 48000.0, "status": "Sent", "due_date": "2026-08-20", "stripe_checkout_url": "https://checkout.stripe.com/pay/cs_test_123", "created_at": "2026-08-02"},
        {"id": "inv-2", "invoice_number": "INV-2026-002", "amount": 12500.0, "status": "Paid", "due_date": "2026-08-01", "stripe_checkout_url": None, "created_at": "2026-08-02"}
    ]

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create new invoice")
async def create_invoice(payload: InvoiceBase):
    return {"id": "inv-3", "invoice_number": payload.invoice_number, "amount": payload.amount, "status": payload.status, "due_date": payload.due_date, "stripe_checkout_url": "https://checkout.stripe.com/pay/cs_test_new", "created_at": "2026-08-02"}

@router.get("/overdue", response_model=List[InvoiceResponse], summary="Get list of overdue unpaid invoices")
async def get_overdue_invoices():
    return [{"id": "inv-99", "invoice_number": "INV-2026-099", "amount": 15000.0, "status": "Overdue", "due_date": "2026-07-25", "stripe_checkout_url": None, "created_at": "2026-07-01"}]

@router.get("/recurring", summary="List automated recurring invoice schedules")
async def list_recurring_invoices():
    return [{"id": "rec-inv-1", "customer": "TechCorp", "interval": "Monthly", "amount": 4000.0, "next_run": "2026-09-01"}]

@router.post("/recurring", response_model=MessageResponse, summary="Create recurring invoice schedule")
async def create_recurring_invoice(customer_id: str, amount: float, interval: str = "Monthly"):
    return {"message": f"Recurring {interval} invoice created for {customer_id}", "status": "success"}

@router.get("/export/csv", summary="Export invoices as CSV")
async def export_invoices_csv():
    return {"download_url": "https://api.crm.com/exports/invoices.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import invoices from CSV")
async def import_invoices_csv():
    return {"message": "Imported 22 invoices", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete invoices")
async def bulk_delete_invoices(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Invoices deleted successfully"}

@router.post("/bulk-remind", response_model=BulkActionResponse, summary="Bulk send payment reminder emails for unpaid invoices")
async def bulk_remind_invoices(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Payment reminders sent"}

@router.get("/{invoice_id}", response_model=InvoiceResponse, summary="Get invoice details by ID")
async def get_invoice(invoice_id: str):
    return {"id": invoice_id, "invoice_number": "INV-2026-001", "amount": 48000.0, "status": "Sent", "due_date": "2026-08-20", "stripe_checkout_url": "https://checkout.stripe.com/pay/cs_test_123", "created_at": "2026-08-02"}

@router.put("/{invoice_id}", response_model=InvoiceResponse, summary="Update invoice details")
async def update_invoice(invoice_id: str, payload: InvoiceBase):
    return {"id": invoice_id, "invoice_number": payload.invoice_number, "amount": payload.amount, "status": payload.status, "due_date": payload.due_date, "stripe_checkout_url": None, "created_at": "2026-08-02"}

@router.delete("/{invoice_id}", response_model=MessageResponse, summary="Delete invoice by ID")
async def delete_invoice(invoice_id: str):
    return {"message": f"Invoice {invoice_id} deleted", "status": "success"}

@router.post("/{invoice_id}/send", response_model=MessageResponse, summary="Email invoice PDF and payment link to client")
async def send_invoice_email(invoice_id: str, recipient_email: str):
    return {"message": f"Invoice email sent to {recipient_email}", "status": "success"}

@router.post("/{invoice_id}/stripe-checkout", summary="Generate fresh Stripe Checkout session URL")
async def create_stripe_checkout(invoice_id: str):
    return {"checkout_url": f"https://checkout.stripe.com/pay/session_{invoice_id}"}

@router.post("/{invoice_id}/mark-paid", response_model=MessageResponse, summary="Manually mark invoice status as Paid")
async def mark_invoice_paid(invoice_id: str, payment_method: str = "Bank Transfer"):
    return {"message": f"Invoice {invoice_id} marked as Paid via {payment_method}", "status": "success"}

@router.post("/{invoice_id}/remind", response_model=MessageResponse, summary="Send payment reminder email for invoice")
async def send_payment_reminder(invoice_id: str):
    return {"message": f"Payment reminder sent for invoice {invoice_id}", "status": "success"}

@router.get("/{invoice_id}/pdf", summary="Get PDF URL for invoice")
async def get_invoice_pdf(invoice_id: str):
    return {"pdf_url": f"https://api.crm.com/invoices/{invoice_id}.pdf"}

@router.post("/{invoice_id}/credit-memo", response_model=MessageResponse, summary="Issue a credit memo adjustment against invoice")
async def issue_credit_memo(invoice_id: str, amount: float, reason: str):
    return {"message": f"Credit memo of ${amount} issued against invoice {invoice_id}", "status": "success"}
