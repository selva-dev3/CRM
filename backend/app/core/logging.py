import json
import logging
import re
import sys

from app.core.config import settings


class RequestIDFilter(logging.Filter):
    """Injects a request_id field into log records for correlation tracing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class SensitiveDataFilter(logging.Filter):
    """Redact credentials that may appear in URLs, headers, or exception text."""

    _quoted_value = r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''
    _authorization_pattern = re.compile(
        r'''(?i)(authorization)(['"]?\s*[:=]\s*)(?:'''
        + _quoted_value
        + r'''|(?:(?:bearer|basic)\s+)?[^&\s,;}]+)'''
    )
    _pattern = re.compile(
        r"(?i)(password|secret|token|id_token|access_token|refresh_token|api_key)"
        + r'''(['"]?\s*[:=]\s*)(?:'''
        + _quoted_value
        + r'''|[^&\s,;}]+)'''
    )

    def filter(self, record: logging.LogRecord) -> bool:
        # Format typed arguments before redacting: converting them to strings
        # first breaks numeric placeholders and mapping-based log messages.
        message = self._authorization_pattern.sub(r"\1\2[REDACTED]", record.getMessage())
        record.msg = self._pattern.sub(r"\1\2[REDACTED]", message)
        record.args = ()
        return True


class WebhookAccessFilter(logging.Filter):
    """Meta verification places a secret in the query string; suppress access logs.

    Channel service logs contain a correlation ID without the query or payload.
    Reverse-proxy access logs must apply the same exclusion (see deployment docs).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "/whatsapp/webhook" not in record.getMessage()


class WhatsAppDiagnosticFormatter(logging.Formatter):
    """Append only channel diagnostic fields; arbitrary extras may contain customer data."""

    counter_fields = (
        "matched_changes", "unmatched_changes", "inserted_messages", "inserted_statuses",
        "duplicate_events",
    )
    state_fields = ("event_status", "message_status", "error_code")
    enum_fields = {
        "message_type": {"text", "image", "audio", "video", "document", "template",
                         "location", "interactive", "button", "contacts", "reaction"},
        "topic": {"greeting", "lead", "deal", "invoice", "payment", "quote", "meeting",
                  "task", "account_owner", "human", "sensitive", "unknown"},
    }

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        if not record.getMessage().startswith("whatsapp."):
            return rendered
        diagnostics = {}
        for field in self.counter_fields:
            value = getattr(record, field, None)
            if type(value) is int and value >= 0:
                diagnostics[field] = value
        for field in self.state_fields:
            value = getattr(record, field, None)
            if isinstance(value, str) and re.fullmatch(r"[A-Z0-9_]{1,80}", value):
                diagnostics[field] = value
        if type(getattr(record, "handoff", None)) is bool:
            diagnostics["handoff"] = record.handoff
        for field, allowed in self.enum_fields.items():
            value = getattr(record, field, None)
            if isinstance(value, str) and value in allowed:
                diagnostics[field] = value
        if diagnostics:
            rendered += " " + json.dumps(diagnostics, sort_keys=True)
        return rendered


def configure_logging() -> None:
    """Configure the root logger with a consistent, correlation-id aware format."""
    level = logging.DEBUG if settings.ENVIRONMENT.lower() == "development" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        WhatsAppDiagnosticFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s"
        )
    )
    handler.addFilter(RequestIDFilter())
    handler.addFilter(SensitiveDataFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").addFilter(WebhookAccessFilter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
