"""Generate quote PDFs from persisted, validated document snapshots."""

from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_quote_pdf(*, organization: dict, customer: dict, quote: dict, items: list[dict]) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm,
        rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=str(quote["quote_number"]))
    styles = getSampleStyleSheet()

    def paragraph(value: object, style="Normal"):
        return Paragraph(escape(str(value or "")), styles[style])

    story = [paragraph("SALES QUOTE", "Title"), Spacer(1, 6 * mm),
        paragraph(organization["name"], "Heading2"), paragraph(organization.get("address")),
        paragraph(organization.get("email")), Spacer(1, 5 * mm),
        paragraph(f"Quote: {quote['quote_number']}", "Heading2"),
        paragraph(f"Currency: {quote['currency']}"),
        paragraph(f"Valid until: {quote.get('expires_at') or 'Awaiting approval'}"),
        paragraph(f"Payment terms: {quote.get('payment_terms') or 'Not specified'}"),
        paragraph(f"Due date: {quote.get('due_date') or 'Not specified'}"),
        Spacer(1, 5 * mm), paragraph("Prepared for", "Heading3"),
        paragraph(customer["company"]), paragraph(customer["name"]), paragraph(customer["email"]),
        Spacer(1, 6 * mm)]
    rows = [[paragraph(label) for label in ("Product / service", "Qty", "Unit price", "Discount %", "Tax %", "Total")]]
    for item in items:
        rows.append([paragraph(item["product_name"]), paragraph(item["quantity"]),
            paragraph(f"{item['unit_price']:.2f}"), paragraph(f"{item['discount_percent']:.2f}"),
            paragraph(f"{item['tax_percent']:.2f}"), paragraph(f"{item['total']:.2f}")])
    table = Table(rows, colWidths=[61 * mm, 12 * mm, 25 * mm, 23 * mm, 18 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#94a3b8")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 6 * mm),
        paragraph(f"Subtotal: {quote['currency']} {sum((item['subtotal'] for item in items), Decimal(0)):.2f}"),
        paragraph(f"Discount: {quote['currency']} {sum((item['discount_total'] for item in items), Decimal(0)):.2f}"),
        paragraph(f"Tax: {quote['currency']} {sum((item['tax_total'] for item in items), Decimal(0)):.2f}"),
        paragraph(f"Grand total: {quote['currency']} {quote['total_amount']:.2f}", "Heading2"),
        paragraph("Review and accept this quote using the secure link in your quote email. "
                  "An invoice is created only after customer acceptance.")])
    document.build(story)
    return output.getvalue()
