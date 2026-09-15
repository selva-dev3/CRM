"""Release smoke check for the API liveness and readiness contracts."""

import os
import time
import urllib.error
import urllib.request
from logging import basicConfig, getLogger
from urllib.parse import urlparse

logger = getLogger("health-smoke")
basicConfig(level="INFO", format="%(levelname)s %(message)s")


def check(path: str, expected_status: int) -> None:
    base_url = os.environ.get("HEALTHCHECK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        logger.error("invalid HEALTHCHECK_BASE_URL scheme or host")
        raise SystemExit(1)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(  # noqa: S310 - scheme is validated above
            f"{base_url}{path}", timeout=5
        ) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.HTTPError) as exc:
        logger.error("health check failed path=%s: %s", path, exc)
        raise SystemExit(1) from exc

    elapsed = time.monotonic() - started
    if status != expected_status:
        logger.error("health check failed path=%s status=%s body=%s", path, status, body)
        raise SystemExit(1)
    if elapsed > 5:
        logger.error(
            f"health check exceeded latency budget path={path} elapsed={elapsed:.2f}s",
        )
        raise SystemExit(1)
    logger.info("health check passed path=%s status=%s elapsed=%.2fs", path, status, elapsed)


if __name__ == "__main__":
    check("/health/live", 200)
    check("/health/ready", 200)
