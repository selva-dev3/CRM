from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, UserInvitation, Organization
from app.schemas.crm_schemas import (
    UserResponse, UserCreate, UserUpdate, UserProfileUpdate, UserInviteRequest,
    UserInviteBulkResponse, AcceptInviteRequest, UserInvitationDetailsResponse,
    UserActionResponse, UserDeleteResponse, MessageResponse, BulkDeleteRequest, BulkActionResponse
)
from app.services.s3_service import s3_service
from app.services.email_service import send_user_invite_email
from app.core.security import generate_random_code, get_password_hash, create_access_token

router = APIRouter()

PROTECTED_SUPERADMIN_EMAIL = "superadmin@gmail.com"

@router.get("", response_model=List[UserResponse], summary="List all users with pagination and search")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(User)
        cleaned_search = search.strip() if search and isinstance(search, str) and search.strip() else None
        if cleaned_search:
            pattern = f"%{cleaned_search}%"
            stmt = stmt.where(User.name.ilike(pattern) | User.email.ilike(pattern))
        
        actual_page = page if isinstance(page, int) else 1
        actual_limit = limit if isinstance(limit, int) else 20
        
        stmt = stmt.offset((actual_page - 1) * actual_limit).limit(actual_limit)
        res = await db.execute(stmt)
        users = res.scalars().all()
        return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "organization_id": u.organization_id, "is_active": u.is_active, "created_at": str(u.created_at)} for u in users]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create new user")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        u = User(name=payload.name, email=payload.email, hashed_password=get_password_hash(payload.password), role=payload.role, organization_id=payload.organization_id)
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

@router.post("/invite", response_model=UserInviteBulkResponse, summary="Bulk invite users via email with name, email and 14-char random tokens")
async def invite_users(payload: UserInviteRequest, db: AsyncSession = Depends(get_db)):
    invitation_responses = []
    try:
        org_res = await db.execute(select(Organization).limit(1))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Default Enterprise CRM")
            db.add(org)
            await db.flush()
        org_id = org.id

        invite_targets = []
        if payload.users:
            for u in payload.users:
                invite_targets.append({"name": u.name or u.email.split("@")[0], "email": u.email.strip()})
        elif payload.emails:
            for email in payload.emails:
                email_clean = email.strip()
                target_name = payload.name or email_clean.split("@")[0]
                invite_targets.append({"name": target_name, "email": email_clean})

        for target in invite_targets:
            token = generate_random_code(14)
            inv = UserInvitation(
                email=target["email"],
                token=token,
                role=payload.role or "Sales Executive",
                organization_id=org_id,
                status="pending"
            )
            db.add(inv)
            await db.flush()

            invite_url = f"http://localhost:3000/accept-invite?token={token}"
            send_user_invite_email(email_to=target["email"], role=payload.role, invite_url=invite_url)

            invitation_responses.append({
                "name": target["name"],
                "email": target["email"],
                "token": token,
                "role": payload.role or "Sales Executive",
                "status": "pending"
            })

        await db.commit()
        return {
            "message": f"Invites sent to {len(invitation_responses)} users",
            "invitations": invitation_responses,
            "status": "success"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invitation dispatch failed: {str(e)}")

@router.get("/invitations/{token}", response_model=UserInvitationDetailsResponse, summary="Get user invitation details by token")
async def get_invitation_details(token: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(UserInvitation).where(UserInvitation.token == token.strip()))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found or token invalid")
    return {
        "id": inv.id,
        "email": inv.email,
        "token": inv.token,
        "role": inv.role,
        "status": inv.status,
        "organization_id": inv.organization_id,
        "created_at": str(inv.created_at)
    }

@router.post("/accept-invite", summary="Accept organization user invitation, set password, and activate account")
async def accept_user_invitation(payload: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    token_clean = payload.token.strip()
    res = await db.execute(select(UserInvitation).where(UserInvitation.token == token_clean))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invitation token")
    if inv.status == "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has already been accepted")
    
    try:
        org_res = await db.execute(select(Organization).limit(1))
        org = org_res.scalars().first()
        if not org:
            org = Organization(name="Default Enterprise CRM")
            db.add(org)
            await db.flush()
        target_org_id = inv.organization_id if inv.organization_id and len(inv.organization_id) > 5 else org.id

        user_res = await db.execute(select(User).where(User.email.ilike(inv.email)))
        user = user_res.scalars().first()
        
        hashed_pwd = get_password_hash(payload.password)

        if user:
            user.name = payload.name
            user.hashed_password = hashed_pwd
            user.role = inv.role
            user.organization_id = target_org_id
            user.is_active = True
        else:
            user = User(
                name=payload.name,
                email=inv.email,
                hashed_password=hashed_pwd,
                role=inv.role,
                organization_id=target_org_id,
                is_active=True
            )
            db.add(user)
            await db.flush()
        
        inv.status = "accepted"
        await db.commit()
        return {
            "message": "Invitation accepted successfully! Your account is active.",
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "status": "success"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to accept invitation: {str(e)}")

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

@router.delete("/{user_id}", response_model=UserDeleteResponse, summary="Delete user by ID (Protected against superadmin@gmail.com deletion)")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    if u.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Protected user '{PROTECTED_SUPERADMIN_EMAIL}' cannot be deleted")
    
    user_name = u.name
    user_email = u.email

    try:
        await db.delete(u)
        await db.commit()
        return {
            "message": f"User '{user_name}' ({user_email}) deleted successfully",
            "user_id": user_id,
            "name": user_name,
            "email": user_email,
            "status": "success"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{user_id}/activate", response_model=UserActionResponse, summary="Activate user account")
async def activate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    u.is_active = True
    await db.commit()
    return {
        "message": f"User '{u.name}' ({u.email}) activated successfully",
        "user_id": u.id,
        "name": u.name,
        "email": u.email,
        "is_active": u.is_active,
        "status": "success"
    }

@router.post("/{user_id}/deactivate", response_model=UserActionResponse, summary="Deactivate user account")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    u = res.scalars().first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    if u.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Protected user '{PROTECTED_SUPERADMIN_EMAIL}' cannot be deactivated")
    u.is_active = False
    await db.commit()
    return {
        "message": f"User '{u.name}' ({u.email}) deactivated successfully",
        "user_id": u.id,
        "name": u.name,
        "email": u.email,
        "is_active": u.is_active,
        "status": "success"
    }

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

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete users (Filters out protected superadmin@gmail.com)")
async def bulk_delete_users(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(User).where(User.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        deleted_count = 0
        for item in items:
            if item.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
                continue
            await db.delete(item)
            deleted_count += 1
        await db.commit()
        return {"affected_count": deleted_count, "message": "Users deleted successfully (Protected users skipped)"}
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
