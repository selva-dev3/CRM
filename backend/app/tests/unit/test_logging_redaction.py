import logging

import pytest

from app.core.logging import SensitiveDataFilter, WhatsAppDiagnosticFormatter


def test_whatsapp_diagnostics_survive_formatting_without_arbitrary_extras():
    record = logging.LogRecord("whatsapp", logging.INFO, "test", 1,
                               "whatsapp.webhook_received", (), None)
    record.inserted_messages = 2
    record.unmatched_changes = 1
    record.body = "private customer content"
    record.access_token = "synthetic-credential"  # noqa: S105 - test-only redaction probe
    record.error_code = "unsafe value with spaces"
    formatted = WhatsAppDiagnosticFormatter("%(message)s").format(record)
    assert '"inserted_messages": 2' in formatted
    assert '"unmatched_changes": 1' in formatted
    assert "private customer" not in formatted
    assert "synthetic-credential" not in formatted
    assert "unsafe value" not in formatted


@pytest.mark.parametrize(
    ("message", "arguments", "expected"),
    [
        ("HTTP status %d", (403,), "HTTP status 403"),
        ("token=%s status=%d", ("synthetic-value", 403), "token=[REDACTED] status=403"),
        ("password=%(value)s count=%(count)d", ({"value": "synthetic-value", "count": 2},), "password=[REDACTED] count=2"),
    ],
)
def test_sensitive_filter_formats_typed_arguments_and_redacts_values(message, arguments, expected):
    record = logging.LogRecord("security", logging.WARNING, "test", 1, message, arguments, None)
    assert SensitiveDataFilter().filter(record) is True
    assert record.getMessage() == expected
    assert record.args == ()
    # Multiple handlers may apply the filter to the same record.
    assert SensitiveDataFilter().filter(record) is True
    assert record.getMessage() == expected


@pytest.mark.parametrize("message,arguments", [
    ("Authorization: Bearer synthetic-credential", ()),
    ("authorization=Basic synthetic-credential", ()),
    ("Authorization: Bearer %s status=%d", ("synthetic-credential", 403)),
    ("%s", ({"Authorization": "Bearer synthetic-credential"},)),
    ('{"token": "synthetic-credential"}', ()),
    ("%s", ({"password": "synthetic-credential with spaces"},)),
    ('{"access_token": "synthetic-credential\\\"escaped"}', ()),
])
def test_sensitive_filter_removes_complete_plain_and_quoted_credentials(message, arguments):
    record = logging.LogRecord("security", logging.WARNING, "test", 1, message, arguments, None)
    SensitiveDataFilter().filter(record)
    assert "synthetic-credential" not in record.getMessage()
    assert "escaped" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
