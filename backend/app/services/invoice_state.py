from app.core.errors import APIException

INVOICE_STATUSES = {"Draft", "Pending", "Overdue", "Paid"}
INVOICE_TRANSITIONS: dict[str, set[str]] = {
    "Draft": {"Draft", "Pending", "Overdue"},
    "Pending": {"Pending", "Overdue", "Paid"},
    "Overdue": {"Overdue", "Pending", "Paid"},
    "Paid": {"Paid"},
}


def assert_invoice_transition(current: str | None, target: str) -> None:
    current_status = current or "Draft"
    if target not in INVOICE_STATUSES or target not in INVOICE_TRANSITIONS.get(current_status, set()):
        raise APIException(
            message=f"Invoice cannot transition from '{current_status}' to '{target}'",
            code="INVALID_INVOICE_TRANSITION",
            status_code=409,
        )
