from app.core.errors import APIException

QUOTE_DRAFT = "Draft"
QUOTE_PENDING_APPROVAL = "Pending Approval"
QUOTE_APPROVED = "Approved"
QUOTE_SENT = "Sent"
QUOTE_ACCEPTED = "Accepted"
QUOTE_REJECTED = "Rejected"

QUOTE_STATUSES = {
    QUOTE_DRAFT,
    QUOTE_PENDING_APPROVAL,
    QUOTE_APPROVED,
    QUOTE_SENT,
    QUOTE_ACCEPTED,
    QUOTE_REJECTED,
}

QUOTE_TRANSITIONS: dict[str, set[str]] = {
    # Internal users prepare and send quotes. Customer approval is recorded
    # only by the public acceptance flow after the quote has been sent.
    QUOTE_DRAFT: {QUOTE_DRAFT, QUOTE_PENDING_APPROVAL, QUOTE_SENT, QUOTE_REJECTED},
    QUOTE_PENDING_APPROVAL: {QUOTE_PENDING_APPROVAL, QUOTE_SENT, QUOTE_REJECTED},
    QUOTE_APPROVED: {QUOTE_APPROVED, QUOTE_SENT},
    QUOTE_SENT: {QUOTE_SENT, QUOTE_ACCEPTED, QUOTE_REJECTED},
    QUOTE_ACCEPTED: {QUOTE_ACCEPTED},
    QUOTE_REJECTED: {QUOTE_REJECTED},
}


def assert_quote_transition(current: str | None, target: str) -> None:
    current_status = current or QUOTE_DRAFT
    if target not in QUOTE_STATUSES or target not in QUOTE_TRANSITIONS.get(current_status, set()):
        raise APIException(
            message=f"Quote cannot transition from '{current_status}' to '{target}'",
            code="INVALID_QUOTE_TRANSITION",
            status_code=409,
        )
