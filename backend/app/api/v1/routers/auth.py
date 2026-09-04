from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.auth_cookies import (
    clear_auth_cookie,
    clear_refresh_cookie,
    set_auth_cookie,
    set_refresh_cookie,
)
from app.core.config import settings
from app.core.errors import APIException
from app.core.rate_limiter import (
    AUTH_LOGIN_RATE_LIMIT,
    AUTH_LOGOUT_RATE_LIMIT,
    AUTH_MAGIC_LINK_REQUEST_RATE_LIMIT,
    AUTH_MAGIC_LINK_VERIFY_RATE_LIMIT,
    AUTH_OAUTH_RATE_LIMIT,
    AUTH_PASSWORD_RESET_CONFIRM_RATE_LIMIT,
    AUTH_PASSWORD_RESET_REQUEST_RATE_LIMIT,
    AUTH_REFRESH_RATE_LIMIT,
    AUTH_REGISTER_RATE_LIMIT,
    USER_INVITATION_ACCEPT_RATE_LIMIT,
    USER_INVITATION_LOOKUP_RATE_LIMIT,
    limiter,
)
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    AcceptInviteRequest,
    ApiKeyCreate,
    ApiKeyResponse,
    LoginRequest,
    MessageResponse,
    OAuthLoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    Token,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserInvitationDetailsResponse,
)
from app.services.auth_service import auth_service
from app.services.email_service import send_welcome_email

router = APIRouter()


def _set_token_cookies(response: Response, result: dict, *, persistent_access: bool = True) -> dict:
    set_auth_cookie(response, result["access_token"], persistent=persistent_access)
    refresh_token = result.get("refresh_token")
    if refresh_token:
        set_refresh_cookie(response, refresh_token)
    return result | {"refresh_token": None}


@router.post("/login", response_model=Token, summary="Authenticate user & return JWT token")
@limiter.limit(AUTH_LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.login(db, payload)
    return _set_token_cookies(response, result, persistent_access=payload.remember_me)


@router.get("/me", summary="Get current authenticated user info with DB role and permissions")
async def get_current_user_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.get_current_user_me(db, user=current_user)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register new tenant & admin user",
)
@limiter.limit(AUTH_REGISTER_RATE_LIMIT)
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(db, payload)


@router.post("/refresh-token", response_model=Token, summary="Refresh JWT access token")
@limiter.limit(AUTH_REFRESH_RATE_LIMIT)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    refresh_token_value = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not refresh_token_value:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Refresh token missing",
        )
    result = await auth_service.refresh_token(db, refresh_token_value)
    return _set_token_cookies(response, result)


@router.post("/logout", response_model=MessageResponse, summary="Invalidate current session")
@limiter.limit(AUTH_LOGOUT_RATE_LIMIT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.logout(db, request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME))
    clear_auth_cookie(response)
    clear_refresh_cookie(response)
    return result


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Trigger password reset email with 14-char random code",
)
@limiter.limit(AUTH_PASSWORD_RESET_REQUEST_RATE_LIMIT)
async def forgot_password(
    request: Request, payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    return await auth_service.forgot_password(db, payload)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a single-use token",
)
@limiter.limit(AUTH_PASSWORD_RESET_CONFIRM_RATE_LIMIT)
async def reset_password(
    request: Request,
    payload: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.reset_password(db, payload)


@router.post(
    "/change-password", response_model=MessageResponse, summary="Change current user password"
)
async def change_password(
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.change_password(
        db,
        current_user,
        payload.old_password,
        payload.new_password,
    )


@router.post(
    "/2fa/setup", response_model=TwoFactorSetupResponse, summary="Setup 2FA TOTP secret & QR"
)
async def setup_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.setup_2fa(db, current_user)


@router.post("/2fa/verify", response_model=MessageResponse, summary="Verify 2FA TOTP code")
async def verify_2fa(
    payload: TwoFactorVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.verify_2fa(db, current_user, payload)


@router.post("/2fa/disable", response_model=MessageResponse, summary="Disable 2FA authentication")
async def disable_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.disable_2fa(db, current_user)


@router.post("/oauth/google", response_model=Token, summary="Google OAuth SSO Login")
@limiter.limit(AUTH_OAUTH_RATE_LIMIT)
async def google_oauth(
    request: Request,
    payload: OAuthLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.google_oauth(db, payload)
    return _set_token_cookies(response, result)


@router.post("/oauth/microsoft", response_model=Token, summary="Microsoft Azure AD SSO Login")
@limiter.limit(AUTH_OAUTH_RATE_LIMIT)
async def microsoft_oauth(
    request: Request,
    payload: OAuthLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.microsoft_oauth(db, payload)
    return _set_token_cookies(response, result)


@router.get(
    "/invitations/{token}",
    response_model=UserInvitationDetailsResponse,
    summary="Get user invitation details by token (Public endpoint)",
)
@limiter.limit(USER_INVITATION_LOOKUP_RATE_LIMIT)
async def get_auth_invitation_details(
    request: Request, token: str, db: AsyncSession = Depends(get_db)
):
    return await auth_service.get_auth_invitation_details(db, token)


@router.post(
    "/accept-invite",
    summary="Accept user invitation, set password, and activate account (Public endpoint)",
)
@limiter.limit(USER_INVITATION_ACCEPT_RATE_LIMIT)
async def accept_auth_user_invitation(
    request: Request,
    payload: AcceptInviteRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.accept_auth_user_invitation(db, payload)
    background_tasks.add_task(
        send_welcome_email,
        email_to=result["email"],
        user_name=result["name"],
        role=result["role"],
    )
    return _set_token_cookies(response, result)


@router.get("/sessions", summary="List active user sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.list_sessions(db, current_user)


@router.delete(
    "/sessions/{session_id}", response_model=MessageResponse, summary="Revoke specific user session"
)
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.revoke_session(db, session_id, current_user)


@router.post(
    "/magic-link/request", response_model=MessageResponse, summary="Request passwordless login link"
)
@limiter.limit(AUTH_MAGIC_LINK_REQUEST_RATE_LIMIT)
async def request_magic_link(request: Request, email: str, db: AsyncSession = Depends(get_db)):
    return await auth_service.request_magic_link(db, email)


@router.post(
    "/magic-link/verify", response_model=Token, summary="Verify passwordless magic link token"
)
@limiter.limit(AUTH_MAGIC_LINK_VERIFY_RATE_LIMIT)
async def verify_magic_link(
    request: Request,
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.verify_magic_link(db, token)
    return _set_token_cookies(response, result)


@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    summary="List organization API keys",
    dependencies=[Depends(require_permission("integrations:apikeys"))],
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.list_api_keys(db, current_user)


@router.post(
    "/api-keys",
    response_model=ApiKeyResponse,
    summary="Create new API key",
    dependencies=[Depends(require_permission("integrations:apikeys"))],
)
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.create_api_key(db, payload, current_user)
