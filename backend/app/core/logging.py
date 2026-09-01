import logging
import sys

from app.core.config import settings


class RequestIDFilter(logging.Filter):
    """Injects a request_id field into log records for correlation tracing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
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

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
