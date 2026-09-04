from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

USER_INVITATION_LOOKUP_RATE_LIMIT = "10/minute"
USER_INVITATION_ACCEPT_RATE_LIMIT = "5/minute"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.rate_limit_storage_uri,
    key_prefix="crm-api",
    key_style="endpoint",
    in_memory_fallback_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RateLimitExceeded):
        raise TypeError("Rate-limit handler received an unexpected exception type")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "code": "RATE_LIMITED",
            "message": "Too many requests. Please try again later.",
            "fields": None,
        },
        headers={"Retry-After": "60"},
    )
