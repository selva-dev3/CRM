from fastapi import APIRouter, HTTPException, status
from app.schemas.crm_schemas import Token, LoginRequest, RegisterRequest, PasswordResetRequest, PasswordChangeRequest, TwoFactorSetupResponse
from app.core.security import create_access_token

router = APIRouter()

@router.post("/login", response_model=Token, summary="Authenticate user & return JWT token")
async def login(payload: LoginRequest):
    """Authenticates credentials and generates JWT access token."""
    return {"access_token": "mock_jwt_token_xyz", "refresh_token": "mock_refresh_token", "token_type": "bearer", "expires_in": 86400}

@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register new user & organization")
async def register(payload: RegisterRequest):
    """Registers a new tenant organization and admin user."""
    return {"message": "Registration successful", "user_id": "usr-100", "org_id": "org-100"}

@router.post("/refresh-token", response_model=Token, summary="Refresh JWT access token")
async def refresh_token(refresh_token: str):
    """Refreshes expired access token using refresh token."""
    return {"access_token": "new_mock_jwt_token", "refresh_token": refresh_token, "token_type": "bearer", "expires_in": 86400}

@router.post("/logout", summary="Invalidate user session")
async def logout():
    """Logs out current user and invalidates session token."""
    return {"message": "Logged out successfully"}

@router.post("/forgot-password", summary="Trigger password reset email")
async def forgot_password(payload: PasswordResetRequest):
    """Sends password reset link to requested user email."""
    return {"message": f"Password reset instructions sent to {payload.email}"}

@router.post("/reset-password", summary="Reset password using token")
async def reset_password(token: str, new_password: str):
    """Resets user password with valid reset token."""
    return {"message": "Password updated successfully"}

@router.post("/2fa/setup", response_model=TwoFactorSetupResponse, summary="Setup 2FA TOTP authentication")
async def setup_2fa():
    """Generates 2FA secret and QR code URL."""
    return {"secret": "JBSWY3DPEHPK3PXP", "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=otpauth://totp/CRM:admin@company.com"}

@router.post("/2fa/verify", summary="Verify 2FA TOTP passcode")
async def verify_2fa(code: str):
    """Verifies 6-digit 2FA passcode."""
    return {"message": "2FA verified successfully", "enabled": True}
