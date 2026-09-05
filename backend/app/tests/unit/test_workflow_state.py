import pytest

from app.core.errors import APIException
from app.services.invoice_state import assert_invoice_transition
from app.services.quote_state import assert_quote_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [("Draft", "Pending Approval"), ("Pending Approval", "Approved"), ("Approved", "Sent"),
     ("Sent", "Accepted"), ("Sent", "Rejected"), ("Accepted", "Accepted")],
)
def test_quote_state_machine_allows_business_transitions(current, target):
    assert_quote_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [("Accepted", "Draft"), ("Accepted", "Approved"), ("Rejected", "Sent"),
     ("Sent", "Draft")],
)
def test_quote_state_machine_rejects_backward_transitions(current, target):
    with pytest.raises(APIException) as exc_info:
        assert_quote_transition(current, target)
    assert exc_info.value.code == "INVALID_QUOTE_TRANSITION"


def test_invoice_paid_requires_verified_transition_path():
    assert_invoice_transition("Pending", "Paid")
    with pytest.raises(APIException):
        assert_invoice_transition("Draft", "Paid")
    with pytest.raises(APIException):
        assert_invoice_transition("Paid", "Draft")
