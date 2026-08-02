from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.crm_schemas import UserResponse, UserCreate, UserUpdate

router = APIRouter()

@router.get("/", response_model=List[UserResponse], summary="List all organization users")
async def list_users(limit: int = 50, offset: int = 0):
    """Retrieves paginated list of active users in organization."""
    return [
        {"id": "usr-1", "name": "Sarah Connor", "email": "sarah@acme.com", "role": "Sales Manager", "organization_id": "org-1", "is_active": True, "created_at": "2026-08-01T10:00:00Z"},
        {"id": "usr-2", "name": "John Matrix", "email": "john@acme.com", "role": "Sales Executive", "organization_id": "org-1", "is_active": True, "created_at": "2026-08-01T11:00:00Z"},
    ]

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user")
async def create_user(payload: UserCreate):
    """Creates a new user account within organization."""
    return {"id": "usr-3", "name": payload.name, "email": payload.email, "role": payload.role, "organization_id": payload.organization_id, "is_active": payload.is_active, "created_at": "2026-08-02T12:00:00Z"}

@router.get("/{user_id}", response_model=UserResponse, summary="Get user details")
async def get_user(user_id: str):
    """Retrieves user profile details by ID."""
    return {"id": user_id, "name": "Sarah Connor", "email": "sarah@acme.com", "role": "Sales Manager", "organization_id": "org-1", "is_active": True, "created_at": "2026-08-01T10:00:00Z"}

@router.patch("/{user_id}", response_model=UserResponse, summary="Update user profile")
async def update_user(user_id: str, payload: UserUpdate):
    """Updates user role or active status."""
    return {"id": user_id, "name": payload.name or "Sarah Connor", "email": "sarah@acme.com", "role": payload.role or "Sales Manager", "organization_id": "org-1", "is_active": True, "created_at": "2026-08-01T10:00:00Z"}

@router.delete("/{user_id}", summary="Delete user account")
async def delete_user(user_id: str):
    """Deactivates and removes user account."""
    return {"message": f"User {user_id} deleted successfully"}
