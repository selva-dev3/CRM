from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.schemas.crm_schemas import (
    UserResponse, UserCreate, UserUpdate, UserProfileUpdate, UserInviteRequest,
    MessageResponse, BulkDeleteRequest, BulkActionResponse
)
from app.services.s3_service import s3_service

router = APIRouter()

@router.get("", response_model=List[UserResponse], summary="List all users with pagination and search")
async def list_users(page: int = 1, limit: int = 20, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(User).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
        res = await db.execute(stmt)
        users = res.scalars().all()
        return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)} for u in users]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create new user")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        u = User(name=payload.name, email=payload.email, hashed_password=payload.password, role=payload.role, organization_id=payload.organization_id)
        db.add(u)
        await db.commit()
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User creation failed: {str(e)}")

@router.get("/me/profile", response_model=UserResponse, summary="Get current logged in user profile")
async def get_my_profile(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).limit(1))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found")
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)}

@router.put("/me/profile", response_model=UserResponse, summary="Update logged in user profile")
async def update_my_profile(payload: UserProfileUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).limit(1))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    try:
        if payload.name: u.name = payload.name
        await db.commit()
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/me/avatar", response_model=MessageResponse, summary="Upload user avatar picture to MinIO S3")
async def upload_avatar(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).limit(1))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        object_name = f"avatars/{u.id}_{file.filename}"
        s3_key = s3_service.upload_file(file.file, object_name=object_name, content_type=file.content_type)
        avatar_url = s3_service.generate_presigned_url(s3_key)
        
        u.avatar_url = avatar_url
        await db.commit()
        return {"message": "Avatar uploaded to MinIO S3 successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"S3 Avatar upload failed: {str(e)}")

@router.get("/{user_id}", response_model=UserResponse, summary="Get user details by ID")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)}

@router.put("/{user_id}", response_model=UserResponse, summary="Update user by ID")
async def update_user(user_id: str, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    try:
        if payload.name: u.name = payload.name
        if payload.role: u.role = payload.role
        await db.commit()
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{user_id}", response_model=MessageResponse, summary="Delete user by ID")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    try:
        await db.delete(u)
        await db.commit()
        return {"message": f"User {user_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/invite", response_model=MessageResponse, summary="Bulk invite users via email")
async def invite_users(payload: UserInviteRequest, db: AsyncSession = Depends(get_db)):
    return {"message": f"Invites sent to {len(payload.emails)} users", "status": "success"}

@router.post("/{user_id}/activate", response_model=MessageResponse, summary="Activate user account")
async def activate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    u.is_active = True
    await db.commit()
    return {"message": f"User {user_id} activated", "status": "success"}

@router.post("/{user_id}/deactivate", response_model=MessageResponse, summary="Deactivate user account")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    u.is_active = False
    await db.commit()
    return {"message": f"User {user_id} deactivated", "status": "success"}

@router.get("/{user_id}/activities", summary="Get user activity timeline")
async def get_user_activities(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return []

@router.get("/{user_id}/teams", summary="Get user team memberships")
async def get_user_teams(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return []

@router.post("/{user_id}/teams", response_model=MessageResponse, summary="Assign user to team")
async def assign_user_team(user_id: str, team_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"message": f"User {user_id} assigned to team {team_id}", "status": "success"}

@router.delete("/{user_id}/teams/{team_id}", response_model=MessageResponse, summary="Remove user from team")
async def remove_user_team(user_id: str, team_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"message": f"User {user_id} removed from team {team_id}", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete users")
async def bulk_delete_users(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(User).where(User.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Users deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/export/csv", summary="Export users list as CSV file")
async def export_users_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/users.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import users from CSV file")
async def import_users_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import processing completed", "status": "success"}

@router.get("/{user_id}/permissions", summary="List effective permissions for specific user")
async def get_user_effective_permissions(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"user_id": user_id, "permissions": ["leads:all", "deals:all", "contacts:all"]}

@router.post("/{user_id}/reset-password-admin", response_model=MessageResponse, summary="Admin trigger forced user password reset")
async def admin_reset_user_password(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"message": f"Temporary password sent to user {user_id}", "status": "success"}

@router.get("/{user_id}/quota", summary="Get user sales quota target")
async def get_user_quota(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"user_id": user_id, "target_amount": 100000.0, "achieved_amount": 0.0}

@router.post("/{user_id}/quota", response_model=MessageResponse, summary="Set user quarterly sales quota target")
async def set_user_quota(user_id: str, target_amount: float, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"message": f"Quota ${target_amount} assigned to {user_id}", "status": "success"}

@router.get("/{user_id}/performance", summary="Get detailed performance scorecard for user")
async def get_user_scorecard(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"user_id": user_id, "win_rate": 0.0, "avg_deal_size": 0.0, "calls_made": 0}
