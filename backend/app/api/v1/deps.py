import json
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
from app.core.logging import get_logger
from app.core.permissions import effective_organization_id
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models import ApiKey, Organization, User, UserSession
from app.services.auth_service import api_key_scope_allows, auth_service

# HTTP Bearer scheme auto-configured for FastAPI Swagger UI authentication
security_scheme = HTTPBearer(auto_error=False)
logger = get_logger(__name__)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate a production JWT supplied by Bearer header or HttpOnly cookie."""
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials.strip()
    elif request.cookies.get(settings.AUTH_COOKIE_NAME):
        raw_token = request.cookies[settings.AUTH_COOKIE_NAME].strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session is required to access this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Developer API keys are hashed at the boundary and resolve to the key's
    # creating user, preserving the existing organization/RBAC checks below.
    if raw_token.startswith("crm_live_"):
        api_key = await db.scalar(
            select(ApiKey).where(ApiKey.key_hash == sha256(raw_token.encode()).hexdigest())
        )
        if (
            api_key is None
            or not api_key.is_active
            or (api_key.expires_at is not None and api_key.expires_at <= datetime.now(UTC))
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key invalid, revoked, or expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await db.get(User, api_key.created_by) if api_key.created_by else None
        organization = await db.get(Organization, api_key.organization_id)
        if (
            user is None
            or not user.is_active
            or user.organization_id != api_key.organization_id
            or organization is None
            or not organization.is_active
            or organization.status != "active"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key owner is unavailable",
                headers={"WWW-Authenticate": "Bearer"},
            )
        api_key.last_used = datetime.now(UTC)
        api_key.usage_count += 1
        await db.commit()
        try:
            parsed_scopes = json.loads(api_key.scopes or "[]")
        except ValueError:
            parsed_scopes = (api_key.scopes or "").split(",")
        user.__dict__["_api_key_scopes"] = {
            str(scope).strip().lower() for scope in parsed_scopes if str(scope).strip()
        }
        return user

    token = raw_token
    user_id = None

    # 1. Try decoding standard JWT token
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require_sub": True,
                "require_exp": True,
                "require_iat": True,
                "require_jti": True,
            },
        )
        if payload.get("token_type") != "access":
            raise JWTError("wrong token type")
        user_id = payload.get("sub")
    except JWTError:
        user_id = None

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token invalid or expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Lookup user in database
    res = await db.execute(select(User).where((User.id == user_id) | (User.email == user_id)))
    user = res.scalars().first()

    if not user or not user.is_active:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_ACCOUNT_INACTIVE",
            message="User session is inactive or account has been removed",
        )

    now = datetime.now(UTC)
    access_session = await db.get(UserSession, sha256(token.encode("utf-8")).hexdigest())
    if (
        access_session is None
        or not access_session.is_current
        or access_session.revoked_at is not None
        or (access_session.expires_at is not None and access_session.expires_at <= now)
        or access_session.user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_session.last_used_at = now
    await apply_organization_context(db, user, request.headers.get("X-Organization-ID"))
    return user


async def apply_organization_context(
    db: AsyncSession, user: User, requested_organization_id: str | None
) -> None:
    """Authorize selection without writing organization membership to the database."""
    platform_admin = getattr(user, "is_platform_admin", False) is True
    if platform_admin:
        user.__dict__.pop("_request_organization_id", None)
    organization_id = requested_organization_id or user.organization_id
    if requested_organization_id and not platform_admin and requested_organization_id != user.organization_id:
        raise ForbiddenError(message="You cannot select another organization")
    if not organization_id:
        if platform_admin:
            return
        raise ForbiddenError(message="Authenticated user has no current organization")
    organization = await db.get(Organization, organization_id)
    if not organization or not organization.is_active or organization.status != "active":
        raise ForbiddenError(message="Selected organization is inactive or unavailable", code="ORGANIZATION_UNAVAILABLE")
    if platform_admin:
        user.__dict__["_request_organization_id"] = organization_id


async def require_user_session(current_user: User = Depends(get_current_user)) -> User:
    """Account security and credential management require a human login session."""
    if getattr(current_user, "_api_key_scopes", None) is not None:
        raise ForbiddenError(message="A user login session is required for this operation")
    return current_user


async def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if getattr(current_user, "is_platform_admin", False) is not True or getattr(
        current_user, "_api_key_scopes", None
    ) is not None:
        raise ForbiddenError(message="Platform Super Admin access is required")
    return current_user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    try:
        return await get_current_user(
            request=request,
            credentials=credentials,
            db=db,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


async def get_valid_org_id(db: AsyncSession, current_user: User | None = None) -> str:
    """Resolve only the authenticated user's organization; never fall back across tenants."""
    if current_user and effective_organization_id(current_user):
        user_org_id = effective_organization_id(current_user)
        res = await db.execute(select(Organization).where(Organization.id == user_org_id))
        if user_org_id and res.scalars().first():
            return user_org_id
    raise ForbiddenError(message="Authenticated user has no valid current organization")


async def authorize_permission(db: AsyncSession, current_user: User, permission: str) -> User:
    """Authorize one explicit permission outside FastAPI's static dependency graph."""
    keys = await auth_service.get_user_permissions(db, current_user)
    if permission not in keys:
        logger.warning(
            "Authorization denied user_id=%s organization_id=%s permission=%s",
            getattr(current_user, "id", None),
            effective_organization_id(current_user),
            permission,
        )
        raise ForbiddenError(message=f"Missing required permission: {permission}")
    if not api_key_scope_allows(current_user, permission):
        logger.warning(
            "API key authorization denied user_id=%s organization_id=%s permission=%s",
            getattr(current_user, "id", None),
            effective_organization_id(current_user),
            permission,
        )
        raise ForbiddenError(message=f"API key is missing required scope: {permission.lower()}")
    return current_user


def require_permission(permission: str):
    """Dependency factory enforcing that the authenticated user holds a specific permission key.

    Uses the RBAC permission model (Permission/RolePermission/UserRole tables) via the
    existing auth_service permission resolution. Raises 403/FORBIDDEN when the permission
    is missing.
    """

    async def permission_dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        return await authorize_permission(db, current_user, permission)

    return permission_dependency
