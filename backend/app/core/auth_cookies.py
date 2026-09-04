from fastapi import Response

from app.core.config import settings


def set_auth_cookie(response: Response, access_token: str, *, persistent: bool = True) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        max_age=(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 if persistent else None),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def set_refresh_cookie(response: Response, refresh_token: str, *, persistent: bool = True) -> None:
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60 if persistent else None),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=f"{settings.API_V1_STR}/auth",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path=f"{settings.API_V1_STR}/auth",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
