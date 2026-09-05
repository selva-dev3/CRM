from decimal import Decimal

from app.services.quote_pdf_service import render_quote_pdf


def sample_quote_pdf() -> bytes:
    return render_quote_pdf(
        organization={"name": "Document QA organization", "address": "Sample business address",
                      "email": "billing@example.test"},
        customer={"company": "Document QA customer", "name": "Sample recipient", "email": "buyer@example.test"},
        quote={"quote_number": "QA-QUOTE", "currency": "INR", "expires_at": "Test validity date",
               "total_amount": Decimal("212.40")},
        items=[{"product_name": "Service & support <annual>", "quantity": 2,
                "unit_price": Decimal("100.00"), "discount_percent": Decimal("10.00"),
                "tax_percent": Decimal("18.00"), "subtotal": Decimal("200.00"),
                "discount_total": Decimal("20.00"), "tax_total": Decimal("32.40"),
                "total": Decimal("212.40")}],
    )


def test_quote_pdf_is_real_document(tmp_path):
    pdf = sample_quote_pdf()
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf
    assert len(pdf) > 1000
    (tmp_path / "quote.pdf").write_bytes(pdf)
