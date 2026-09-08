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


def configure_logging() -> None:
    """Configure the root logger with a consistent, correlation-id aware format."""
    level = logging.DEBUG if settings.ENVIRONMENT.lower() == "development" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s"
        )
    )
    handler.addFilter(RequestIDFilter())
    handler.addFilter(SensitiveDataFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
