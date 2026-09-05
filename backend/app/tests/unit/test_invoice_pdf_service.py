from decimal import Decimal

from app.services.invoice_pdf_service import render_invoice_pdf, render_receipt_pdf


def test_invoice_pdf_renders_real_document_from_snapshots():
    content = render_invoice_pdf(
        organization={"name": "Acme CRM", "address": "Chennai", "email": "billing@acme.test"},
        customer={"company": "Buyer Ltd", "contact": "Priya", "email": "priya@buyer.test"},
        invoice={
            "invoice_number": "INV-2026-000001",
            "quote_number": "QUO-2026-000001",
            "due_date": "2026-10-01",
            "currency": "INR",
            "subtotal": Decimal("1000.00"),
            "discount_total": Decimal("100.00"),
            "tax_total": Decimal("162.00"),
            "amount": Decimal("1062.00"),
        },
        items=[
            {
                "product_name": "CRM License",
                "quantity": 1,
                "unit_price": Decimal("1000.00"),
                "discount_percent": Decimal("10.00"),
                "tax_percent": Decimal("18.00"),
                "total": Decimal("1062.00"),
            }
        ],
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_receipt_pdf_renders_only_verified_payment_snapshot():
    content = render_receipt_pdf(
        organization={"name": "Acme CRM", "address": "Chennai"},
        customer={"company": "Buyer Ltd", "email": "priya@buyer.test"},
        invoice={"invoice_number": "INV-2026-000001"},
        payment={
            "payment_id": "payment-1",
            "provider_reference": "pi-1",
            "paid_at": "2026-09-05T10:00:00+00:00",
            "payment_method": "card",
            "currency": "INR",
            "amount": Decimal("1062.00"),
        },
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
