from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.core.security import create_access_token, get_password_hash, verify_password

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(payload: LoginRequest):
    if payload.email == "admin@crm.com" and payload.password == "admin123":
        access_token = create_access_token(subject="user_admin_id")
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    return {"message": "User registered successfully", "email": payload.email}
