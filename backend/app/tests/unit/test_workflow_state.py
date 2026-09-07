import pytest

from app.core.errors import APIException
from app.services.invoice_state import assert_invoice_transition
from app.services.quote_state import assert_quote_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("Draft", "Pending Approval"),
        ("Pending Approval", "Approved"),
        ("Pending Approval", "Draft"),
        ("Approved", "Sent"),
        ("Sent", "Accepted"),
        ("Sent", "Rejected"),
        ("Accepted", "Accepted"),
    ],
)
def test_quote_state_machine_allows_business_transitions(current, target):
    assert_quote_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("Pending Approval", "Sent"),
        ("Accepted", "Draft"),
        ("Accepted", "Approved"),
        ("Rejected", "Sent"),
        ("Sent", "Draft"),
    ],
)
def test_quote_state_machine_rejects_backward_transitions(current, target):
    with pytest.raises(APIException) as exc_info:
        assert_quote_transition(current, target)
    assert exc_info.value.code == "INVALID_QUOTE_TRANSITION"


@pytest.mark.parametrize(
    "current,target",
    [
        ("Draft", "In Review"),
        ("In Review", "Finalized"),
        ("In Review", "Draft"),
        ("Finalized", "Accepted"),
        ("Draft", "Cancelled"),
        ("Finalized", "Cancelled"),
        ("Accepted", "Cancelled"),
        ("Draft", "Draft"),
        ("Finalized", "Finalized"),
        ("Accepted", "Accepted"),
    ],
)
def test_invoice_lifecycle_transitions(current, target):
    assert_invoice_transition(current, target)


@pytest.mark.parametrize(
    "current,target",
    [
        ("Draft", "Accepted"),
        ("Draft", "Finalized"),
        ("In Review", "Accepted"),
        ("Finalized", "Draft"),
        ("Accepted", "Draft"),
        ("Cancelled", "Finalized"),
        ("Draft", "Paid"),
        ("Finalized", "Paid"),
        ("Accepted", "Pending"),
    ],
)
def test_invoice_rejects_backward_and_payment_status_transitions(current, target):
    with pytest.raises(APIException) as exc:
        assert_invoice_transition(current, target)
    assert exc.value.status_code == 409
    assert exc.value.code == "INVALID_INVOICE_TRANSITION"
