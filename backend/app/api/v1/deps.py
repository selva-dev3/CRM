from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ForbiddenError
from app.core.permissions import UserRole, check_permission
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models import Organization, User
from app.services.auth_service import auth_service

# HTTP Bearer scheme auto-configured for FastAPI Swagger UI authentication
security_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    token_query: str | None = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Validate a JWT supplied by Bearer header, HttpOnly cookie, or query string.

    Legacy mock-token formats remain available only in development and test.
    """
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials.strip()
    elif request.cookies.get(settings.AUTH_COOKIE_NAME):
        raw_token = request.cookies[settings.AUTH_COOKIE_NAME].strip()
    elif token_query:
        raw_token = token_query.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token missing: Authorization Bearer header is required to access this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = raw_token
    user_id = None

    # 1. Try decoding standard JWT token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        pass

    # 2. Fallback helper for mock/dev token formats (e.g. "jwt_token_<id>", email, or raw ID)
    allow_mock_tokens = settings.ENVIRONMENT.lower() in {"development", "test"}
    if not user_id and allow_mock_tokens:
        if token.startswith("jwt_token_"):
            user_id = token.replace("jwt_token_", "")
        elif "@" in token:
            res_email = await db.execute(select(User).where(User.email.ilike(token)))
            u_email = res_email.scalars().first()
            if u_email:
                return u_email
        elif len(token) > 5:
            user_id = token

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session is inactive or account has been removed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    token_query: str | None = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db)
) -> User | None:
    try:
        return await get_current_user(
            request=request,
            credentials=credentials,
            token_query=token_query,
            db=db,
        )
    except Exception:
        return None

async def get_valid_org_id(db: AsyncSession, current_user: User | None = None) -> str:
    """Helper function that guarantees a valid Organization foreign key exists in database."""
    if current_user and getattr(current_user, 'organization_id', None):
        user_org_id = current_user.organization_id
        res = await db.execute(select(Organization).where(Organization.id == user_org_id))
        if res.scalars().first():
            return user_org_id

    res = await db.execute(select(Organization).limit(1))
    existing_org = res.scalars().first()
    if existing_org:
        return existing_org.id

    default_org = Organization(
        id="org-1",
        name="Default Organization",
        slug="default-org",
        status="active"
    )
    db.add(default_org)
    await db.commit()
    return default_org.id


def require_role(*roles: UserRole):
    """Dependency factory enforcing that the authenticated user holds one of the given roles."""
    async def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if not check_permission(current_user.role, list(roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_dependency


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
        keys = await auth_service.get_user_permissions(db, current_user)
        if permission not in keys:
            raise ForbiddenError(message=f"Missing required permission: {permission}")
        return current_user

    return permission_dependency
