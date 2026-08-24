from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
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
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
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


def _make_org(**overrides):
    defaults = {
        "id": "org-1",
        "name": "Acme Inc",
        "status": "active",
        "is_active": True,
    }
    defaults.update(overrides)
    return type("Org", (), defaults)()


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


    monkeypatch.setattr(
        "app.services.user_service.get_password_hash", lambda pwd: f"hashed-{pwd}"
    )

    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")
    result = await service.create_user(db, payload, current_user=current_user)

    assert result["email"] == "alex@crm.com"
    assert repo.create.await_args.kwargs["data"]["role"] == "role-1"
    assert repo.create.await_args.kwargs["data"]["hashed_password"] == "hashed-secret"
    assert repo.create.await_args.kwargs["data"]["organization_id"] == "org-1"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_derives_org_from_authenticated_user():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org(id="org-current"))

    current_user = _make_user(id="current-user", organization_id="org-current")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    await service.create_user(db, payload, current_user=current_user)

    assert service.organization_repository.get_by_id.await_args.args[1] == "org-current"
    assert repo.create.await_args.kwargs["data"]["organization_id"] == "org-current"


@pytest.mark.asyncio
async def test_create_user_rejects_role_from_another_organization():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": "org-other"})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org(id="org-1"))

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_allows_system_role_with_no_org():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Admin", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org(id="org-1"))

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    await service.create_user(db, payload, current_user=current_user)

    assert repo.create.await_args.kwargs["data"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_create_user_missing_current_org_returns_403():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    current_user = _make_user(id="current-user", organization_id=None)
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_current_org_not_found_returns_404():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.organization_repository.get_by_id = AsyncMock(return_value=None)

    current_user = _make_user(id="current-user", organization_id="org-missing")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 404
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_inactive_org_denied():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org(status="inactive"))

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-1", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_rejects_unknown_role():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=None)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="not-a-real-role", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_rejects_system_role():
    repo = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    service.role_repository.get_role_by_id_or_name = AsyncMock(
        return_value=type(
            "R",
            (),
            {"id": "role-admin", "name": "Admin", "organization_id": None, "is_system_role": True},
        )()
    )
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(name="Alex Smith", email="alex@crm.com", role="role-admin", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403
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
async def test_accept_invitation_rejects_missing_organization(monkeypatch):
    inv = _make_invitation(organization_id=None)
    repo = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)
    service.role_repository.get_user_role_mapping = AsyncMock(return_value=None)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: "hashed")

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token="ABCDEFGHIJKLMN", name="Alex", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    assert "organization" in exc_info.value.message.lower()
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted_does_not_commit():
    inv = _make_invitation(status="accepted")
    repo = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token="ABCDEFGHIJKLMN", name="Alex", password="secret")

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    db.commit.assert_not_awaited()
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_users_uses_current_user_org_and_stores_role_id(monkeypatch):
    repo = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None, "is_system_role": False})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    monkeypatch.setattr("app.services.user_service.send_user_invite_email", lambda **kwargs: None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")
    result = await service.invite_users(db, payload, current_user=current_user)

    assert result["invitations"][0]["role"] == "role-1"
    assert repo.create_invitation.await_args.kwargs["data"]["role"] == "role-1"
    assert repo.create_invitation.await_args.kwargs["data"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_invite_users_derives_org_from_session_not_payload():
    repo = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-2")
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org(id="org-2"))
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": "org-2", "is_system_role": False})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")
    await service.invite_users(db, payload, current_user=current_user)

    assert repo.create_invitation.await_args.kwargs["data"]["organization_id"] == "org-2"


@pytest.mark.asyncio
async def test_invite_users_rejects_unknown_role():
    repo = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="not-a-real-role")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_invite_users_rejects_role_from_other_org():
    repo = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    role = type("R", (), {"id": "role-9", "name": "Rival Manager", "organization_id": "org-99", "is_system_role": False})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-9")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_invite_users_rejects_system_role():
    repo = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    role = type("R", (), {"id": "role-admin", "name": "Admin", "organization_id": None, "is_system_role": True})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-admin")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403


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
    role = type("R", (), {"id": "role-9", "name": "Sales Manager", "organization_id": None})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    result = await service.update_user(
        db, "user-1", UserUpdate(role="Sales Manager"), current_user=_make_user(role="Admin")
    )

    assert user.role == "role-9"
    assert user.name == "Alex Smith"
    assert result["role"] == "role-9"


@pytest.mark.asyncio
async def test_update_user_rejects_role_from_other_org():
    user = _make_user(organization_id="org-1")
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-9", "name": "Foreign Role", "organization_id": "org-2"})()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    with pytest.raises(APIException) as exc_info:
        await service.update_user(
            db, "user-1", UserUpdate(role="role-9"), current_user=_make_user(role="Admin")
        )
    assert exc_info.value.status_code == 400
    assert user.role == "Sales Executive"


@pytest.mark.asyncio
async def test_update_user_rejects_system_role():
    user = _make_user()
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type(
        "R",
        (),
        {"id": "role-9", "name": "Admin", "organization_id": None, "is_system_role": True},
    )()
    service.role_repository.get_role_by_id_or_name = AsyncMock(return_value=role)

    with pytest.raises(ForbiddenError):
        await service.update_user(
            db, "user-1", UserUpdate(role="role-9"), current_user=_make_user(role="Admin")
        )
    assert user.role == "Sales Executive"

@pytest.mark.asyncio
async def test_get_user_quota_returns_target_and_real_achieved():
    user = _make_user()
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.get_quota = AsyncMock(
        return_value=type("Q", (), {"target_amount": 100000.0})()
    )
    repo.total_won_revenue = AsyncMock(return_value=45000.0)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_user_quota(db, "user-1", current_user=_make_user(role="Admin"))

    assert result["user_id"] == "user-1"
    assert result["target_amount"] == 100000.0
    assert result["achieved_amount"] == 45000.0


@pytest.mark.asyncio
async def test_get_user_quota_without_configured_quota_is_none():
    user = _make_user()
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.get_quota = AsyncMock(return_value=None)
    repo.total_won_revenue = AsyncMock(return_value=12000.5)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_user_quota(db, "user-1", current_user=_make_user(role="Admin"))

    assert result["target_amount"] is None
    assert result["achieved_amount"] == 12000.5


@pytest.mark.asyncio
async def test_set_user_quota_persists_and_commits():
    user = _make_user()
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.upsert_quota = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.set_user_quota(
        db, user_id="user-1", target_amount=250000.0, current_user=_make_user(role="Admin")
    )

    repo.upsert_quota.assert_awaited_once_with(
        db, user_id="user-1", organization_id="org-1", target_amount=250000.0
    )
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_set_user_quota_rejects_negative_target():
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.set_user_quota(
            db, user_id="user-1", target_amount=-1.0, current_user=_make_user(role="Admin")
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_get_user_quota_rejects_cross_org_target():
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=_make_user(organization_id="org-other"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_user_quota(db, "user-1", current_user=_make_user(role="Admin"))


@pytest.mark.asyncio
async def test_set_user_quota_rejects_cross_org_target():
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=_make_user(organization_id="org-other"))
    repo.upsert_quota = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.set_user_quota(
            db, user_id="user-1", target_amount=1000.0, current_user=_make_user(role="Admin")
        )
    repo.upsert_quota.assert_not_awaited()
