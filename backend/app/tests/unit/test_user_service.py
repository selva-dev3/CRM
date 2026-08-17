from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User, UserInvitation
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import UserCreate, UserUpdate
from app.services.user_service import UserService, user_to_dict


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed",
        "role": "Sales Executive",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_invitation(**overrides) -> UserInvitation:
    defaults = {
        "id": "inv-1",
        "email": "invite@crm.com",
        "token": "ABCDEFGHIJKLMN",
        "role": "Sales Executive",
        "organization_id": "org-1",
        "status": "pending",
    }
    defaults.update(overrides)
    return UserInvitation(**defaults)


def _service_with(repo: UserRepository) -> UserService:
    return UserService(repository=repo)


@pytest.mark.asyncio
async def test_list_users_maps_role_names():
    user = _make_user(role="role-uuid-1")
    repo = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.role_name_map = AsyncMock(
        return_value={"role-uuid-1": "Sales Manager", "Sales Manager": "Sales Manager"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None)

    assert result[0]["role"] == "Sales Manager"


@pytest.mark.asyncio
async def test_list_users_fallback_role_for_superadmin():
    user = _make_user(role=None, email="superadmin@gmail.com")
    repo = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.role_name_map = AsyncMock(return_value={})
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None)

    assert result[0]["role"] == "Super Administrator"


@pytest.mark.asyncio
async def test_get_user_raises_not_found_when_missing():
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_user(db, "missing-user")


@pytest.mark.asyncio
async def test_create_user_hashes_password(monkeypatch):
    user = _make_user()
    repo = UserRepository()
    repo.create = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.user_service import get_password_hash

    monkeypatch.setattr(
        "app.services.user_service.get_password_hash", lambda pwd: f"hashed-{pwd}"
    )

    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", organization_id="org-1", password="secret"
    )
    result = await service.create_user(db, payload)

    assert result["email"] == "alex@crm.com"
    assert repo.create.await_args.kwargs["data"]["role"] == "role-1"
    assert repo.create.await_args.kwargs["data"]["hashed_password"] == "hashed-secret"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_rejects_unknown_role():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=None)

    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="not-a-real-role", organization_id="org-1", password="secret"
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_protects_superadmin():
    user = _make_user(email="superadmin@gmail.com")
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.delete_user(db, "user-1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_protects_superadmin():
    user = _make_user(email="superadmin@gmail.com")
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.deactivate_user(db, "user-1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_bulk_delete_skips_superadmin():
    repo = UserRepository()
    repo.list_by_ids = AsyncMock(
        return_value=[_make_user(id="u1", email="a@crm.com"), _make_user(id="u2", email="superadmin@gmail.com")]
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_users(db, ["u1", "u2"])

    assert result["affected_count"] == 1


@pytest.mark.asyncio
async def test_accept_invitation_creates_user(monkeypatch):
    inv = _make_invitation()
    user = _make_user()
    repo = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.get_first_org = AsyncMock(return_value=type("O", (), {"id": "org-1"})())
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=user)
    repo.list_invitations_by_email = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.role_repository.get_user_role_mapping = AsyncMock(return_value=None)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: "hashed")

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token="ABCDEFGHIJKLMN", name="Alex", password="secret")
    result = await service.accept_user_invitation(db, payload)

    assert result["user_id"] == "user-1"
    assert inv.status == "accepted"
    assert repo.create.await_args.kwargs["data"]["role"] == "role-1"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_accept_invitation_rejects_invalid_role(monkeypatch):
    inv = _make_invitation(role="vanished-role")
    repo = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=None)

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token="ABCDEFGHIJKLMN", name="Alex", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_users_validates_role(monkeypatch):
    repo = UserRepository()
    repo.get_first_org = AsyncMock(return_value=type("O", (), {"id": "org-1"})())
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    monkeypatch.setattr("app.services.user_service.send_user_invite_email", lambda **kwargs: None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")
    result = await service.invite_users(db, payload)

    assert result["invitations"][0]["role"] == "Sales Manager"
    assert repo.create_invitation.await_args.kwargs["data"]["role"] == "Sales Manager"


@pytest.mark.asyncio
async def test_invite_users_rejects_unknown_role():
    repo = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="not-a-real-role")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_my_profile_raises_not_found_when_no_users():
    repo = UserRepository()
    repo.get_first = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_my_profile(db)


def test_user_to_dict_serializes_all_fields():
    u = _make_user()
    assert user_to_dict(u)["role"] == "Sales Executive"
    assert user_to_dict(u)["is_active"] is True


@pytest.mark.asyncio
async def test_update_user_only_changes_provided_fields():
    user = _make_user()
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_user(db, "user-1", UserUpdate(role="Sales Manager"))

    assert user.role == "Sales Manager"
    assert user.name == "Alex Smith"
    assert result["role"] == "Sales Manager"