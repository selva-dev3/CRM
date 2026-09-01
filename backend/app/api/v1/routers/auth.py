from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.auth_cookies import clear_auth_cookie, set_auth_cookie
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

router = APIRouter()


@router.post("/login", response_model=Token, summary="Authenticate user & return JWT token")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.login(db, payload)
    set_auth_cookie(response, result["access_token"], persistent=payload.remember_me)
    return result


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
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(db, payload)


@router.post("/refresh-token", response_model=Token, summary="Refresh JWT access token")
async def refresh_token(
    refresh_token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.refresh_token(db, refresh_token)
    set_auth_cookie(response, result["access_token"])
    return result


@router.post("/logout", response_model=MessageResponse, summary="Invalidate current session")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clear_auth_cookie(response)
    return {"message": "Logged out successfully", "status": "success"}


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Trigger password reset email with 14-char random code",
)
async def forgot_password(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.forgot_password(db, payload)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a single-use token",
)
async def reset_password(
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
async def google_oauth(
    payload: OAuthLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.google_oauth(db, payload)
    set_auth_cookie(response, result["access_token"])
    return result


@router.post("/oauth/microsoft", response_model=Token, summary="Microsoft Azure AD SSO Login")
async def microsoft_oauth(
    payload: OAuthLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.microsoft_oauth(db, payload)
    set_auth_cookie(response, result["access_token"])
    return result


@router.get(
    "/invitations/{token}",
    response_model=UserInvitationDetailsResponse,
    summary="Get user invitation details by token (Public endpoint)",
)
async def get_auth_invitation_details(token: str, db: AsyncSession = Depends(get_db)):
    return await auth_service.get_auth_invitation_details(db, token)


@router.post(
    "/accept-invite",
    summary="Accept user invitation, set password, and activate account (Public endpoint)",
)
async def accept_auth_user_invitation(
    payload: AcceptInviteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.accept_auth_user_invitation(db, payload)
    set_auth_cookie(response, result["access_token"])
    return result


@router.get("/sessions", summary="List active user sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.list_sessions(db)


@router.delete(
    "/sessions/{session_id}", response_model=MessageResponse, summary="Revoke specific user session"
)
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.revoke_session(db, session_id)


@router.post(
    "/magic-link/request", response_model=MessageResponse, summary="Request passwordless login link"
)
async def request_magic_link(email: str, db: AsyncSession = Depends(get_db)):
    return await auth_service.request_magic_link(db, email)


@router.post(
    "/magic-link/verify", response_model=Token, summary="Verify passwordless magic link token"
)
async def verify_magic_link(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.verify_magic_link(db, token)
    set_auth_cookie(response, result["access_token"])
    return result


@router.get("/api-keys", response_model=list[ApiKeyResponse], summary="List organization API keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.list_api_keys(db)


@router.post("/api-keys", response_model=ApiKeyResponse, summary="Create new API key")
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await auth_service.create_api_key(db, payload)
