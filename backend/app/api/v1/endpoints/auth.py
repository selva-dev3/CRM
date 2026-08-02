from fastapi import APIRouter, HTTPException, status, Query
from typing import List
from app.schemas.crm_schemas import (
    Token, LoginRequest, RegisterRequest, PasswordResetRequest, PasswordChangeRequest,
    TwoFactorSetupResponse, TwoFactorVerifyRequest, OAuthLoginRequest, ApiKeyCreate, ApiKeyResponse,
    MessageResponse
)

router = APIRouter()

@router.post("/login", response_model=Token, summary="Authenticate user & return JWT token")
async def login(payload: LoginRequest):
    return {"access_token": "jwt_token_123", "refresh_token": "refresh_123", "token_type": "bearer", "expires_in": 86400}

@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register new tenant & admin user")
async def register(payload: RegisterRequest):
    return {"message": "Registration successful", "user_id": "usr-100", "org_id": "org-100"}

@router.post("/refresh-token", response_model=Token, summary="Refresh JWT access token")
async def refresh_token(refresh_token: str):
    return {"access_token": "new_jwt_token_456", "refresh_token": refresh_token, "token_type": "bearer", "expires_in": 86400}

@router.post("/logout", response_model=MessageResponse, summary="Invalidate current session")
async def logout():
    return {"message": "Logged out successfully", "status": "success"}

@router.post("/forgot-password", response_model=MessageResponse, summary="Trigger password reset email")
async def forgot_password(payload: PasswordResetRequest):
    return {"message": f"Reset link sent to {payload.email}", "status": "success"}

@router.post("/reset-password", response_model=MessageResponse, summary="Reset password using token")
async def reset_password(token: str, new_password: str):
    return {"message": "Password updated successfully", "status": "success"}

@router.post("/change-password", response_model=MessageResponse, summary="Change current user password")
async def change_password(payload: PasswordChangeRequest):
    return {"message": "Password changed successfully", "status": "success"}

@router.post("/2fa/setup", response_model=TwoFactorSetupResponse, summary="Setup 2FA TOTP secret & QR")
async def setup_2fa():
    return {"secret": "JBSWY3DPEHPK3PXP", "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=otpauth://totp/CRM:user"}

@router.post("/2fa/verify", response_model=MessageResponse, summary="Verify 2FA TOTP code")
async def verify_2fa(payload: TwoFactorVerifyRequest):
    return {"message": "2FA verified successfully", "status": "success"}

@router.post("/2fa/disable", response_model=MessageResponse, summary="Disable 2FA authentication")
async def disable_2fa():
    return {"message": "2FA disabled successfully", "status": "success"}

@router.post("/oauth/google", response_model=Token, summary="Google OAuth SSO Login")
async def google_oauth(payload: OAuthLoginRequest):
    return {"access_token": "google_jwt_token", "refresh_token": "google_refresh", "token_type": "bearer", "expires_in": 86400}

@router.post("/oauth/microsoft", response_model=Token, summary="Microsoft Azure AD SSO Login")
async def microsoft_oauth(payload: OAuthLoginRequest):
    return {"access_token": "ms_jwt_token", "refresh_token": "ms_refresh", "token_type": "bearer", "expires_in": 86400}

@router.get("/sessions", summary="List active user sessions")
async def list_sessions():
    return [{"session_id": "sess-1", "device": "Chrome Windows", "ip": "127.0.0.1", "is_current": True}]

@router.delete("/sessions/{session_id}", response_model=MessageResponse, summary="Revoke specific user session")
async def revoke_session(session_id: str):
    return {"message": f"Session {session_id} revoked", "status": "success"}

@router.post("/magic-link/request", response_model=MessageResponse, summary="Request passwordless login link")
async def request_magic_link(email: str):
    return {"message": f"Magic link sent to {email}", "status": "success"}

@router.post("/magic-link/verify", response_model=Token, summary="Verify passwordless magic link token")
async def verify_magic_link(token: str):
    return {"access_token": "magic_jwt_token", "refresh_token": "magic_refresh", "token_type": "bearer", "expires_in": 86400}

@router.get("/api-keys", response_model=List[ApiKeyResponse], summary="List organization API keys")
async def list_api_keys():
    return [{"id": "key-1", "name": "Zapier Key", "key": "crm_live_xxxxx", "created_at": "2026-08-02", "last_used": "2026-08-02"}]

@router.post("/api-keys", response_model=ApiKeyResponse, summary="Create new API key")
async def create_api_key(payload: ApiKeyCreate):
    return {"id": "key-2", "name": payload.name, "key": "crm_live_newkey123", "created_at": "2026-08-02"}
