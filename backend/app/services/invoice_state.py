from app.core.errors import APIException

INVOICE_STATUSES = {"Draft", "In Review", "Finalized", "Accepted", "Cancelled"}
INVOICE_TRANSITIONS: dict[str, set[str]] = {
    "Draft": {"Draft", "In Review", "Cancelled"},
    "In Review": {"In Review", "Draft", "Finalized", "Cancelled"},
    "Finalized": {"Finalized", "Accepted", "Cancelled"},
    "Accepted": {"Accepted", "Cancelled"},
    "Cancelled": {"Cancelled"},
}


def assert_invoice_transition(current: str | None, target: str) -> None:
    current_status = current or "Draft"
    if target not in INVOICE_STATUSES or target not in INVOICE_TRANSITIONS.get(
        current_status, set()
    ):
        raise APIException(
            message=f"Invoice cannot transition from '{current_status}' to '{target}'",
            code="INVALID_INVOICE_TRANSITION",
            status_code=409,
        )
