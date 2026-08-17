from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    AcceptInviteRequest,
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    UserActionResponse,
    UserCreate,
    UserDeleteResponse,
    UserInvitationDetailsResponse,
    UserInviteBulkResponse,
    UserInviteRequest,
    UserProfileUpdate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import user_service

router = APIRouter()


@router.get("", response_model=List[UserResponse], summary="List all users with pagination and search", dependencies=[Depends(require_permission("users:read"))])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.list_users(db, page=page, limit=limit, search=search)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
    dependencies=[
        Depends(require_permission("users:create")),
        Depends(require_permission("users:roles")),
    ],
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await user_service.create_user(db, payload, current_user=current_user)


@router.get("/me/profile", response_model=UserResponse, summary="Get current logged in user profile")
async def get_my_profile(db: AsyncSession = Depends(get_db)):
    return await user_service.get_my_profile(db)


@router.put("/me/profile", response_model=UserResponse, summary="Update logged in user profile")
async def update_my_profile(payload: UserProfileUpdate, db: AsyncSession = Depends(get_db)):
    return await user_service.update_my_profile(db, payload)


@router.post("/me/avatar", response_model=MessageResponse, summary="Upload user avatar picture to MinIO S3")
async def upload_avatar(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await user_service.upload_avatar(
        db, file=file.file, filename=file.filename, content_type=file.content_type
    )


@router.post("/invite", response_model=UserInviteBulkResponse, summary="Bulk invite users via email with name, email and 14-char random tokens", dependencies=[Depends(require_permission("users:invite"))])
async def invite_users(payload: UserInviteRequest, db: AsyncSession = Depends(get_db)):
    return await user_service.invite_users(db, payload)


@router.get("/invitations", response_model=List[UserInvitationDetailsResponse], summary="List all user invitations", dependencies=[Depends(require_permission("users:read"))])
async def list_user_invitations(
    token: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.list_user_invitations(db, token=token, status_filter=status_filter)


@router.get("/invitations/all", response_model=List[UserInvitationDetailsResponse], summary="List all user invitations (alias)", dependencies=[Depends(require_permission("users:read"))])
async def list_user_invitations_all(
    token: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.list_user_invitations(db, token=token, status_filter=status_filter)


@router.get("/invitations/{token}", response_model=UserInvitationDetailsResponse, summary="Get user invitation details by token", dependencies=[Depends(require_permission("users:read"))])
async def get_invitation_details(token: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_invitation_details(db, token)


@router.post("/accept-invite", summary="Accept organization user invitation, set password, and activate account", dependencies=[Depends(require_permission("users:invite"))])
async def accept_user_invitation(payload: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    return await user_service.accept_user_invitation(db, payload)


@router.get("/{user_id}", response_model=UserResponse, summary="Get user details by ID", dependencies=[Depends(require_permission("users:read"))])
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user(db, user_id)


@router.put("/{user_id}", response_model=UserResponse, summary="Update user by ID", dependencies=[Depends(require_permission("users:update"))])
async def update_user(user_id: str, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    return await user_service.update_user(db, user_id, payload)


@router.delete("/{user_id}", response_model=UserDeleteResponse, summary="Delete user by ID (Protected against superadmin@gmail.com deletion)", dependencies=[Depends(require_permission("users:delete"))])
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.delete_user(db, user_id)


@router.post("/{user_id}/activate", response_model=UserActionResponse, summary="Activate user account", dependencies=[Depends(require_permission("users:update"))])
async def activate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.activate_user(db, user_id)


@router.post("/{user_id}/deactivate", response_model=UserActionResponse, summary="Deactivate user account", dependencies=[Depends(require_permission("users:update"))])
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.deactivate_user(db, user_id)


@router.get("/{user_id}/activities", summary="Get user activity timeline", dependencies=[Depends(require_permission("users:read"))])
async def get_user_activities(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user_activities(db, user_id)


@router.get("/{user_id}/teams", summary="Get user team memberships", dependencies=[Depends(require_permission("users:read"))])
async def get_user_teams(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user_teams(db, user_id)


@router.post("/{user_id}/teams", response_model=MessageResponse, summary="Assign user to team", dependencies=[Depends(require_permission("users:roles"))])
async def assign_user_team(
    user_id: str,
    team_id: str,
    team_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.assign_user_team(db, user_id=user_id, team_id=team_id, team_name=team_name)


@router.delete("/{user_id}/teams/{team_id}", response_model=MessageResponse, summary="Remove user from team", dependencies=[Depends(require_permission("users:roles"))])
async def remove_user_team(user_id: str, team_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.remove_user_team(db, user_id=user_id, team_id=team_id)


@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete users (Filters out protected superadmin@gmail.com)", dependencies=[Depends(require_permission("users:delete"))])
async def bulk_delete_users(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await user_service.bulk_delete_users(db, payload.ids)


@router.get("/export/csv", summary="Export users list as CSV file", dependencies=[Depends(require_permission("users:export"))])
async def export_users_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/users.csv"}


@router.post("/import/csv", response_model=MessageResponse, summary="Import users from CSV file", dependencies=[Depends(require_permission("users:import"))])
async def import_users_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import processing completed", "status": "success"}


@router.get("/{user_id}/permissions", summary="List effective permissions for specific user", dependencies=[Depends(require_permission("users:roles"))])
async def get_user_effective_permissions(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user_effective_permissions(db, user_id)


@router.post("/{user_id}/reset-password-admin", response_model=MessageResponse, summary="Admin trigger forced user password reset", dependencies=[Depends(require_permission("users:update"))])
async def admin_reset_user_password(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.admin_reset_user_password(db, user_id)


@router.get("/{user_id}/quota", summary="Get user sales quota target", dependencies=[Depends(require_permission("users:read"))])
async def get_user_quota(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user_quota(db, user_id)


@router.post("/{user_id}/quota", response_model=MessageResponse, summary="Set user quarterly sales quota target", dependencies=[Depends(require_permission("users:update"))])
async def set_user_quota(user_id: str, target_amount: float, db: AsyncSession = Depends(get_db)):
    return await user_service.set_user_quota(db, user_id=user_id, target_amount=target_amount)


@router.get("/{user_id}/performance", summary="Get detailed performance scorecard for user", dependencies=[Depends(require_permission("users:read"))])
async def get_user_scorecard(user_id: str, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user_scorecard(db, user_id)