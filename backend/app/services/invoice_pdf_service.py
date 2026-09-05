"""Render immutable invoice and payment receipt snapshots as PDF documents."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _paragraph(styles, value: object, style: str = "Normal") -> Paragraph:
    return Paragraph(escape(str(value or "")), styles[style])


def render_invoice_pdf(
    *, organization: dict, customer: dict, invoice: dict, items: list[dict]
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=str(invoice["invoice_number"]),
    )
    styles = getSampleStyleSheet()

    def p(value: object, style: str = "Normal") -> Paragraph:
        return _paragraph(styles, value, style)

    story = [
        p("INVOICE", "Title"),
        Spacer(1, 6 * mm),
        p(organization["name"], "Heading2"),
        p(organization.get("address")),
        p(organization.get("email")),
        Spacer(1, 5 * mm),
        p(f"Invoice: {invoice['invoice_number']}", "Heading2"),
        p(f"Quote: {invoice.get('quote_number') or '-'}"),
        p(f"Due date: {invoice['due_date']}"),
        p(f"Currency: {invoice['currency']}"),
        Spacer(1, 5 * mm),
        p("Bill to", "Heading3"),
        p(customer.get("company")),
        p(customer.get("contact")),
        p(customer.get("email")),
        p(
            ", ".join(
                filter(None, (customer.get("street"), customer.get("city"), customer.get("state")))
            )
        ),
        p(" ".join(filter(None, (customer.get("postal_code"), customer.get("country"))))),
        Spacer(1, 6 * mm),
    ]
    rows = [
        [
            p(label)
            for label in ("Product / service", "Qty", "Unit price", "Discount %", "Tax %", "Total")
        ]
    ]
    for item in items:
        rows.append(
            [
                p(item["product_name"]),
                p(item["quantity"]),
                p(f"{item['unit_price']:.2f}"),
                p(f"{item['discount_percent']:.2f}"),
                p(f"{item['tax_percent']:.2f}"),
                p(f"{item['total']:.2f}"),
            ]
        )
    table = Table(
        rows, colWidths=[61 * mm, 12 * mm, 25 * mm, 23 * mm, 18 * mm, 35 * mm], repeatRows=1
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#94a3b8")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 6 * mm),
            p(f"Subtotal: {invoice['currency']} {invoice['subtotal']:.2f}"),
            p(f"Discount: {invoice['currency']} {invoice['discount_total']:.2f}"),
            p(f"Tax: {invoice['currency']} {invoice['tax_total']:.2f}"),
            p(f"Total due: {invoice['currency']} {invoice['amount']:.2f}", "Heading2"),
            p("Payment is complete only after server-side verification by the payment provider."),
        ]
    )
    document.build(story)
    return output.getvalue()


def render_receipt_pdf(
    *, organization: dict, customer: dict, invoice: dict, payment: dict
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=f"Receipt {payment['payment_id']}",
    )
    styles = getSampleStyleSheet()

    def p(value: object, style: str = "Normal") -> Paragraph:
        return _paragraph(styles, value, style)

    story = [
        p("PAYMENT RECEIPT", "Title"),
        Spacer(1, 8 * mm),
        p(organization["name"], "Heading2"),
        p(organization.get("address")),
        Spacer(1, 6 * mm),
        p(f"Invoice: {invoice['invoice_number']}"),
        p(f"Payment ID: {payment['payment_id']}"),
        p(f"Provider reference: {payment['provider_reference']}"),
        p(f"Payment date: {payment['paid_at']}"),
        p(f"Payment method: {payment.get('payment_method') or 'Stripe'}"),
        Spacer(1, 5 * mm),
        p(f"Received from: {customer.get('company') or customer.get('contact')}"),
        p(customer.get("email")),
        Spacer(1, 8 * mm),
        p(f"Amount paid: {payment['currency']} {payment['amount']:.2f}", "Heading2"),
        p("Payment verified by Stripe."),
    ]
    document.build(story)
    return output.getvalue()
