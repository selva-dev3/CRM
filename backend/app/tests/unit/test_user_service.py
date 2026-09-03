from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User, UserInvitation
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import UserCreate, UserUpdate
from app.services.user_service import UserService, user_to_dict

VALID_INPUT = "secret"
EXPECTED_HASHED_VALUE = "hashed-secret"
TEST_CODE = "ABCDEFGHIJKLMN"


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
        "token": TEST_CODE,
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
    repo: Any = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.role_name_map = AsyncMock(
        return_value={"role-uuid-1": "Sales Manager", "Sales Manager": "Sales Manager"}
    )
    service = _service_with(repo)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None, current_user=_make_user())

    assert result[0]["role"] == "Sales Manager"
    # Listing is tenant scoped to the caller's organization.
    assert repo.list.await_args_list[-1].kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_list_users_fallback_role_for_superadmin():
    user = _make_user(role=None, email="superadmin@gmail.com")
    repo: Any = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.role_name_map = AsyncMock(return_value={})
    service = _service_with(repo)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None, current_user=_make_user())

    assert result[0]["role"] == "Super Administrator"


@pytest.mark.asyncio
async def test_get_user_raises_not_found_when_missing():
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_user(
            db, "missing-user", current_user=_make_user(id="admin", email="admin@crm.com")
        )


@pytest.mark.asyncio
async def test_create_user_hashes_password(monkeypatch):
    user = _make_user()
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: f"hashed-{pwd}")

    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )
    result = await service.create_user(db, payload, current_user=current_user)

    assert result["email"] == "alex@crm.com"
    assert repo.create.await_args_list[-1].kwargs["data"]["role"] == "role-1"
    assert (
        repo.create.await_args_list[-1].kwargs["data"]["hashed_password"] == EXPECTED_HASHED_VALUE
    )
    assert repo.create.await_args_list[-1].kwargs["data"]["organization_id"] == "org-1"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_derives_org_from_authenticated_user():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(id="org-current")
    )

    current_user = _make_user(id="current-user", organization_id="org-current")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    await service.create_user(db, payload, current_user=current_user)

    organization_repository = cast(Any, service.organization_repository)
    assert organization_repository.get_by_id.await_args_list[-1].args[1] == "org-current"
    assert repo.create.await_args_list[-1].kwargs["data"]["organization_id"] == "org-current"


@pytest.mark.asyncio
async def test_create_user_rejects_role_from_another_organization():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type(
        "R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": "org-other"}
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(id="org-1")
    )

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_allows_system_role_with_no_org():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Admin", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(id="org-1")
    )

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    await service.create_user(db, payload, current_user=current_user)

    assert repo.create.await_args_list[-1].kwargs["data"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_create_user_missing_current_org_returns_403():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    current_user = _make_user(id="current-user", organization_id=None)
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_current_org_not_found_returns_404():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=None)

    current_user = _make_user(id="current-user", organization_id="org-missing")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 404
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_inactive_org_denied():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(status="inactive")
    )

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="role-1", password=VALID_INPUT
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 403
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_rejects_unknown_role():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=None)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith", email="alex@crm.com", role="not-a-real-role", password=VALID_INPUT
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_user(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_assigns_system_role():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "id": "role-sales-manager",
                "name": "Sales Manager",
                "organization_id": None,
                "is_system_role": True,
            },
        )()
    )
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())

    current_user = _make_user(id="current-user", organization_id="org-1")
    payload = UserCreate(
        name="Alex Smith",
        email="alex@crm.com",
        role="role-sales-manager",
        password=VALID_INPUT,
    )

    await service.create_user(db, payload, current_user=current_user)

    assert repo.create.await_args.kwargs["data"]["role"] == "role-sales-manager"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_protects_superadmin():
    user = _make_user(email="superadmin@gmail.com")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.delete_user(
            db, "user-1", current_user=_make_user(id="admin", email="admin@crm.com")
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_protects_superadmin():
    user = _make_user(email="superadmin@gmail.com")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.deactivate_user(
            db, "user-1", current_user=_make_user(id="admin", email="admin@crm.com")
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_bulk_delete_skips_superadmin():
    repo: Any = UserRepository()
    repo.list_by_ids = AsyncMock(
        return_value=[
            _make_user(id="u1", email="a@crm.com"),
            _make_user(id="u2", email="superadmin@gmail.com"),
        ]
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_users(
        db, ["u1", "u2"], current_user=_make_user(id="admin", email="admin@crm.com")
    )

    assert result["affected_count"] == 1


@pytest.mark.asyncio
async def test_accept_invitation_creates_user(monkeypatch):
    inv = _make_invitation()
    user = _make_user()
    repo: Any = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.get_first_org = AsyncMock(return_value=type("O", (), {"id": "org-1"})())
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=user)
    repo.list_invitations_by_email = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=None)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: "hashed")

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)
    result = await service.accept_user_invitation(db, payload)

    assert result["user_id"] == "user-1"
    assert inv.status == "accepted"
    assert repo.create.await_args_list[-1].kwargs["data"]["role"] == "role-1"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_accept_invitation_rejects_invalid_role(monkeypatch):
    inv = _make_invitation(role="vanished-role")
    repo: Any = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=None)

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_invitation_rejects_missing_organization(monkeypatch):
    inv = _make_invitation(organization_id=None)
    repo: Any = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=None)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: "hashed")

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    assert "organization" in exc_info.value.message.lower()
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_invitation_already_accepted_does_not_commit():
    inv = _make_invitation(status="accepted")
    repo: Any = UserRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Manager", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import AcceptInviteRequest

    payload = AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)

    with pytest.raises(APIException) as exc_info:
        await service.accept_user_invitation(db, payload)
    assert exc_info.value.status_code == 400
    db.commit.assert_not_awaited()
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_users_uses_current_user_org_and_stores_role_id(monkeypatch):
    repo: Any = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    role = type(
        "R",
        (),
        {"id": "role-1", "name": "Sales Manager", "organization_id": None, "is_system_role": False},
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    monkeypatch.setattr("app.services.user_service.send_user_invite_email", lambda **kwargs: None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")
    result = await service.invite_users(db, payload, current_user=current_user)

    assert result["invitations"][0]["role"] == "role-1"
    assert repo.create_invitation.await_args_list[-1].kwargs["data"]["role"] == "role-1"
    assert repo.create_invitation.await_args_list[-1].kwargs["data"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_invite_users_accepts_normalized_active_organization_status(monkeypatch):
    repo: Any = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(status=" Active ")
    )
    role = type(
        "R",
        (),
        {
            "id": "role-1",
            "name": "Sales Manager",
            "organization_id": "org-1",
            "is_system_role": False,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    monkeypatch.setattr("app.services.user_service.send_user_invite_email", lambda **kwargs: None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")

    result = await service.invite_users(db, payload, current_user=current_user)

    assert result["status"] == "success"
    repo.create_invitation.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("organization", "expected_message"),
    [
        (_make_org(status="inactive"), "Organization is inactive."),
        (_make_org(is_active=False), "Organization is disabled."),
    ],
)
async def test_invite_users_rejects_inactive_or_disabled_organization(
    monkeypatch, organization, expected_message
):
    repo: Any = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=organization)
    role_lookup = AsyncMock()
    cast(Any, service.role_repository).get_role_by_id_or_name = role_lookup
    send_invite = AsyncMock()
    monkeypatch.setattr("app.services.user_service.send_user_invite_email", send_invite)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == expected_message
    role_lookup.assert_not_awaited()
    repo.create_invitation.assert_not_awaited()
    send_invite.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_users_derives_org_from_session_not_payload():
    repo: Any = UserRepository()
    repo.create_invitation = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-2")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_make_org(id="org-2")
    )
    role = type(
        "R",
        (),
        {
            "id": "role-1",
            "name": "Sales Manager",
            "organization_id": "org-2",
            "is_system_role": False,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-1")
    await service.invite_users(db, payload, current_user=current_user)

    assert repo.create_invitation.await_args_list[-1].kwargs["data"]["organization_id"] == "org-2"


@pytest.mark.asyncio
async def test_invite_users_rejects_unknown_role():
    repo: Any = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=None)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="not-a-real-role")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_invite_users_rejects_role_from_other_org():
    repo: Any = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    role = type(
        "R",
        (),
        {
            "id": "role-9",
            "name": "Rival Manager",
            "organization_id": "org-99",
            "is_system_role": False,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    payload = UserInviteRequest(users=[{"email": "invite@crm.com"}], role="role-9")

    with pytest.raises(APIException) as exc_info:
        await service.invite_users(db, payload, current_user=current_user)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_invite_users_assigns_sales_manager_when_system_role(monkeypatch):
    repo: Any = UserRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    role = type(
        "R",
        (),
        {
            "id": "role-sales-manager",
            "name": "Sales Manager",
            "organization_id": None,
            "is_system_role": True,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    from app.schemas.crm_schemas import UserInviteRequest

    monkeypatch.setattr("app.services.user_service.send_user_invite_email", lambda **kwargs: None)
    payload = UserInviteRequest(
        users=[{"email": "invite@crm.com"}], role="role-sales-manager"
    )

    result = await service.invite_users(db, payload, current_user=current_user)

    assert result["status"] == "success"
    assert result["invitations"][0]["role"] == "role-sales-manager"


@pytest.mark.asyncio
async def test_get_my_profile_raises_not_found_when_no_users():
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_my_profile(db, _make_user())


def test_user_to_dict_serializes_all_fields():
    u = _make_user()
    assert user_to_dict(u)["role"] == "Sales Executive"
    assert user_to_dict(u)["is_active"] is True


@pytest.mark.asyncio
async def test_update_user_only_changes_provided_fields():
    user = _make_user()
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-9", "name": "Sales Manager", "organization_id": None})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    mapping = type("Mapping", (), {"role_id": "old-role"})()
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=mapping)

    result = await service.update_user(
        db, "user-1", UserUpdate(role="Sales Manager"), current_user=_make_user(role="Admin")
    )

    assert user.role == "role-9"
    assert user.name == "Alex Smith"
    assert result["role"] == "role-9"
    assert mapping.role_id == "role-9"


@pytest.mark.asyncio
async def test_update_user_rejects_role_from_other_org():
    user = _make_user(organization_id="org-1")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-9", "name": "Foreign Role", "organization_id": "org-2"})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)

    with pytest.raises(APIException) as exc_info:
        await service.update_user(
            db, "user-1", UserUpdate(role="role-9"), current_user=_make_user(role="Admin")
        )
    assert exc_info.value.status_code == 400
    assert user.role == "Sales Executive"


@pytest.mark.asyncio
async def test_update_user_assigns_sales_manager_when_system_role():
    user = _make_user()
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type(
        "R",
        (),
        {
            "id": "role-9",
            "name": "Sales Manager",
            "organization_id": None,
            "is_system_role": True,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=None)

    result = await service.update_user(
        db, "user-1", UserUpdate(role="role-9"), current_user=_make_user(role="Admin")
    )

    assert result["role"] == "role-9"
    assert user.role == "role-9"
    added_mapping = db.add.call_args.args[0]
    assert added_mapping.user_id == "user-1"
    assert added_mapping.role_id == "role-9"


@pytest.mark.asyncio
async def test_get_user_quota_returns_target_and_real_achieved():
    user = _make_user()
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.get_quota = AsyncMock(return_value=type("Q", (), {"target_amount": 100000.0})())
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
    repo: Any = UserRepository()
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
    repo: Any = UserRepository()
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
    repo: Any = UserRepository()
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
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=_make_user(organization_id="org-other"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_user_quota(db, "user-1", current_user=_make_user(role="Admin"))


@pytest.mark.asyncio
async def test_set_user_quota_rejects_cross_org_target():
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=_make_user(organization_id="org-other"))
    repo.upsert_quota = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.set_user_quota(
            db, user_id="user-1", target_amount=1000.0, current_user=_make_user(role="Admin")
        )
    repo.upsert_quota.assert_not_awaited()
