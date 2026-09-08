from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User, UserInvitation
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import UserCreate, UserUpdate
from app.services.user_service import UserService, user_to_dict

VALID_INPUT = "StrongSecret1!"
EXPECTED_HASHED_VALUE = "hashed-StrongSecret1!"


@pytest.mark.parametrize(
    "password",
    [
        "Short1!",
        "ALLUPPERCASE1!",
        "alllowercase1!",
        "NoNumbersHere!",
        "NoSpecialChar1",
    ],
)
def test_user_create_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            name="Alex Smith",
            email="alex@crm.com",
            role="role-1",
            password=password,
        )


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


def _make_org(**overrides):
    defaults = {
        "id": "org-1",
        "name": "Acme Inc",
        "status": "active",
        "is_active": True,
    }
    defaults.update(overrides)
    return type("Org", (), defaults)()



@pytest.fixture(autouse=True)
def invitation_membership_repository(monkeypatch):
    from app.models import OrganizationSubscription
    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository

    for method in ("lock_invitation_email",):
        monkeypatch.setattr(OrganizationLifecycleRepository, method, AsyncMock())
    monkeypatch.setattr(OrganizationLifecycleRepository, "lock_invitation_organization", AsyncMock(return_value=_make_org(max_users=100)))
    monkeypatch.setattr(OrganizationLifecycleRepository, "tenant_member_count", AsyncMock(return_value=0))
    monkeypatch.setattr(OrganizationLifecycleRepository, "subscription_for_membership", AsyncMock(return_value=OrganizationSubscription(current_users=0)))
    for method in ("email_in_use", "pending_invitation_exists", "pending_legacy_invitation_exists"):
        monkeypatch.setattr(OrganizationLifecycleRepository, method, AsyncMock(return_value=False))

def _service_with(repo: UserRepository) -> UserService:
    service = UserService(repository=repo)

    async def lock_resolved_role(db, role_id, organization_id):
        return await service.role_repository.get_role_by_id_or_name(
            db, role_id, organization_id=organization_id
        )

    cast(Any, service.role_repository).get_role_for_update = AsyncMock(
        side_effect=lock_resolved_role
    )
    return service


@pytest.mark.asyncio
async def test_list_users_maps_role_names():
    user = _make_user(role="role-uuid-1")
    repo: Any = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={user.id: "Sales Manager"}
    )
    service = _service_with(repo)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None, current_user=_make_user())

    assert result[0]["role"] == "Sales Manager"
    # Listing is tenant scoped to the caller's organization.
    assert repo.list.await_args_list[-1].kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_list_users_does_not_infer_role_from_email():
    user = _make_user(role=None, email="superadmin@gmail.com")
    repo: Any = UserRepository()
    repo.list = AsyncMock(return_value=[user])
    repo.effective_role_names_for_users = AsyncMock(return_value={})
    service = _service_with(repo)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_users(db, page=1, limit=20, search=None, current_user=_make_user())

    assert result[0]["role"] == "User"


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
async def test_get_user_maps_role_id_to_display_name():
    user = _make_user(role="95efa96f-4d75-46ff-9e2f-183a16f7531d")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.effective_role_names_for_users = AsyncMock(
        return_value={user.id: "Sales Manager"}
    )
    service = _service_with(repo)

    result = await service.get_user(
        AsyncMock(spec=AsyncSession), "user-1", current_user=_make_user(id="admin")
    )

    assert result["role"] == "Sales Manager"


@pytest.mark.asyncio
async def test_create_user_hashes_password(monkeypatch):
    user = _make_user()
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.user_service.get_password_hash", lambda pwd: f"hashed-{pwd}")

    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": "org-1"})()
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
    assert db.add.call_count == 2
    assert any(type(call.args[0]).__name__ == "UserRole" for call in db.add.call_args_list)
    assert any(type(call.args[0]).__name__ == "AuditLog" for call in db.add.call_args_list)


@pytest.mark.asyncio
async def test_create_user_derives_org_from_authenticated_user():
    repo: Any = UserRepository()
    repo.create = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-1", "name": "Sales Executive", "organization_id": "org-current"})()
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
async def test_create_user_rejects_global_system_role():
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

    with pytest.raises(APIException):
        await service.create_user(db, payload, current_user=current_user)
    repo.create.assert_not_awaited()


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
                "organization_id": "org-1",
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
async def test_delete_user_protects_platform_admin():
    user = _make_user(email="platform@example.com", is_platform_admin=True)
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=user)
    repo.lock_active_by_org = AsyncMock(return_value=[user])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={user.id: "Sales Executive"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.delete_user(
            db, "user-1", current_user=_make_user(id="admin", email="admin@crm.com")
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_deactivates_and_preserves_record():
    target = _make_user(id="user-1", email="member@crm.com")
    active_admin = _make_user(id="admin", email="admin@crm.com", role="Admin")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=target)
    repo.lock_active_by_org = AsyncMock(return_value=[target, active_admin])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={target.id: "Sales Executive", active_admin.id: "Admin"}
    )
    repo.delete = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_user(db, target.id, current_user=active_admin)

    assert target.is_active is False
    assert result["status"] == "success"
    repo.delete.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_deactivate_user_rejects_last_active_admin():
    target = _make_user(id="admin-1", email="admin@crm.com", role="Admin")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=target)
    repo.lock_active_by_org = AsyncMock(return_value=[target])
    repo.effective_role_names_for_users = AsyncMock(return_value={target.id: "Admin"})
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.deactivate_user(
            db,
            target.id,
            current_user=_make_user(id="manager", role="Sales Manager"),
        )

    assert exc_info.value.code == "LAST_ADMIN_DEACTIVATION_FORBIDDEN"
    assert target.is_active is True
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_user_rejects_current_user():
    target = _make_user(id="admin-1", email="admin@crm.com", role="Admin")
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=target)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.deactivate_user(db, target.id, current_user=target)

    assert exc_info.value.code == "SELF_DEACTIVATION_FORBIDDEN"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_user_protects_platform_admin():
    user = _make_user(email="platform@example.com", is_platform_admin=True)
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
async def test_bulk_delete_skips_platform_admin():
    regular_user = _make_user(id="u1", email="a@crm.com")
    protected_user = _make_user(id="u2", email="platform@example.com", is_platform_admin=True)
    repo: Any = UserRepository()
    repo.list_by_ids = AsyncMock(return_value=[regular_user, protected_user])
    repo.lock_active_by_org = AsyncMock(return_value=[regular_user, protected_user])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={regular_user.id: "Sales Executive", protected_user.id: "Super Admin"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_users(
        db, ["u1", "u2"], current_user=_make_user(id="admin", email="admin@crm.com")
    )

    assert result["affected_count"] == 1
    assert regular_user.is_active is False
    assert protected_user.is_active is True


@pytest.mark.asyncio
async def test_bulk_delete_keeps_one_active_admin():
    first_admin = _make_user(id="admin-1", email="one@crm.com", role="Admin")
    second_admin = _make_user(id="admin-2", email="two@crm.com", role="Admin")
    repo: Any = UserRepository()
    repo.list_by_ids = AsyncMock(return_value=[first_admin, second_admin])
    repo.lock_active_by_org = AsyncMock(return_value=[first_admin, second_admin])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={first_admin.id: "Admin", second_admin.id: "Admin"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_users(
        db,
        [first_admin.id, second_admin.id],
        current_user=_make_user(id="manager", role="Sales Manager"),
    )

    assert result["affected_count"] == 1
    assert sum(user.is_active for user in (first_admin, second_admin)) == 1


@pytest.mark.asyncio
async def test_invite_users_uses_current_user_org_and_stores_role_id(monkeypatch):
    repo: Any = UserRepository()
    repo.create_invitation = AsyncMock(return_value=UserInvitation(id="inv-test"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(id="user-1", organization_id="org-1")
    cast(Any, service.organization_repository).get_by_id = AsyncMock(return_value=_make_org())
    role = type(
        "R",
        (),
        {"id": "role-1", "name": "Sales Manager", "organization_id": "org-1", "is_system_role": False},
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
    repo.create_invitation = AsyncMock(return_value=UserInvitation(id="inv-test"))
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
    repo.create_invitation = AsyncMock(return_value=UserInvitation(id="inv-test"))
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
    repo.create_invitation = AsyncMock(return_value=UserInvitation(id="inv-test"))
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
            "organization_id": "org-1",
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
    repo.lock_active_by_org = AsyncMock(return_value=[user])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={user.id: "Sales Executive"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type("R", (), {"id": "role-9", "name": "Sales Manager", "organization_id": "org-1"})()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    mapping = type("Mapping", (), {"role_id": "old-role"})()
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=mapping)
    cast(Any, service.role_repository).replace_user_role = AsyncMock()

    result = await service.update_user(
        db, "user-1", UserUpdate(role="Sales Manager"), current_user=_make_user(role="Admin")
    )

    assert user.role == "role-9"
    assert user.name == "Alex Smith"
    assert result["role"] == "role-9"
    cast(Any, service.role_repository).replace_user_role.assert_awaited_once_with(
        db, user.id, "role-9"
    )


@pytest.mark.asyncio
async def test_update_user_rejects_last_admin_demotion():
    admin = _make_user(id="admin-1", role="Admin")
    replacement = type(
        "R",
        (),
        {"id": "read-only", "name": "Read Only", "organization_id": "org-1"},
    )()
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=admin)
    repo.lock_active_by_org = AsyncMock(return_value=[admin])
    repo.effective_role_names_for_users = AsyncMock(return_value={admin.id: "Admin"})
    service = _service_with(repo)
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(
        return_value=replacement
    )
    cast(Any, service.role_repository).replace_user_role = AsyncMock()

    with pytest.raises(APIException) as exc_info:
        await service.update_user(
            AsyncMock(spec=AsyncSession),
            admin.id,
            UserUpdate(role=replacement.id),
            current_user=_make_user(id="manager", role="Sales Manager"),
        )

    assert exc_info.value.code == "LAST_ADMIN_DEACTIVATION_FORBIDDEN"
    cast(Any, service.role_repository).replace_user_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_uses_authoritative_mapping_for_non_uuid_last_admin():
    admin = _make_user(id="admin-1", role="stale-read-only")
    replacement = type(
        "R",
        (),
        {"id": "read-only", "name": "Read Only", "organization_id": "org-1"},
    )()
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=admin)
    repo.lock_active_by_org = AsyncMock(return_value=[admin])
    repo.effective_role_names_for_users = AsyncMock(return_value={admin.id: "Admin"})
    service = _service_with(repo)
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(
        return_value=replacement
    )
    cast(Any, service.role_repository).replace_user_role = AsyncMock()

    with pytest.raises(APIException) as exc_info:
        await service.update_user(
            AsyncMock(spec=AsyncSession),
            admin.id,
            UserUpdate(role=replacement.id),
            current_user=_make_user(id="manager", role="Sales Manager"),
        )

    assert exc_info.value.code == "LAST_ADMIN_DEACTIVATION_FORBIDDEN"
    cast(Any, service.role_repository).replace_user_role.assert_not_awaited()


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
    repo.lock_active_by_org = AsyncMock(return_value=[user])
    repo.effective_role_names_for_users = AsyncMock(
        return_value={user.id: "Sales Executive"}
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    role = type(
        "R",
        (),
        {
            "id": "role-9",
            "name": "Sales Manager",
            "organization_id": "org-1",
            "is_system_role": True,
        },
    )()
    cast(Any, service.role_repository).get_role_by_id_or_name = AsyncMock(return_value=role)
    cast(Any, service.role_repository).get_user_role_mapping = AsyncMock(return_value=None)
    cast(Any, service.role_repository).replace_user_role = AsyncMock()

    result = await service.update_user(
        db, "user-1", UserUpdate(role="role-9"), current_user=_make_user(role="Admin")
    )

    assert result["role"] == "role-9"
    assert user.role == "role-9"
    cast(Any, service.role_repository).replace_user_role.assert_awaited_once_with(
        db, "user-1", "role-9"
    )


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


@pytest.mark.asyncio
async def test_invitation_batch_failure_rolls_back_and_sends_no_email(monkeypatch):
    from unittest.mock import Mock

    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
    from app.schemas.crm_schemas import UserInviteRequest

    repo = UserRepository()
    repo.create_invitation = AsyncMock(return_value=UserInvitation(id="inv-test"))
    service = _service_with(repo)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    service._resolve_assignable_role = AsyncMock(return_value=type("Role", (), {"id": "role-1", "name": "Sales Executive"})())
    monkeypatch.setattr(OrganizationLifecycleRepository, "email_in_use", AsyncMock(side_effect=[False, True]))
    send = Mock()
    monkeypatch.setattr("app.services.user_service.send_user_invite_email", send)
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as error:
        await service.invite_users(db, UserInviteRequest(
            users=[{"email": "first@example.com"}, {"email": "second@example.com"}], role="role-1"
        ), current_user=_make_user())
    assert error.value.status_code == 409
    repo.create_invitation.assert_awaited_once()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
    send.assert_not_called()


@pytest.mark.asyncio
async def test_direct_user_creation_enforces_member_limit_before_writes(monkeypatch):
    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository

    repo = UserRepository()
    repo.create = AsyncMock()
    service = _service_with(repo)
    service.organization_repository.get_by_id = AsyncMock(return_value=_make_org())
    monkeypatch.setattr(OrganizationLifecycleRepository, "tenant_member_count", AsyncMock(return_value=100))
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as error:
        await service.create_user(db, UserCreate(
            name="New User", email="new@example.com", role="role-1", password=VALID_INPUT
        ), current_user=_make_user())
    assert error.value.status_code == 409
    repo.create.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
