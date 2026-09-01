from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class APIException(Exception):
    """Base domain exception mapped to the standardized error response shape."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "API_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        fields: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.fields = fields
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class UnauthorizedError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ForbiddenError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


def _error_payload(code: str, message: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "fields": fields}


async def _api_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, APIException):
        raise TypeError("API exception handler received an unexpected exception type")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message, exc.fields),
    )


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise TypeError("HTTP exception handler received an unexpected exception type")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("HTTP_ERROR", str(exc.detail)),
    )


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError("Validation exception handler received an unexpected exception type")
    fields: dict[str, Any] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []))
        fields[loc or "body"] = err.get("msg", "Invalid value")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload("VALIDATION_ERROR", "Request validation failed", fields),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while handling %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            "INTERNAL_ERROR", "An unexpected error occurred. Please try again later."
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIException, _api_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
