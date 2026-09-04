"""Cross-organization tenancy tests for every user-by-id endpoint.

Guards the IDOR fix: any authenticated user may only read/mutate users
belonging to their own organization; foreign-org ids must behave exactly
like missing ones (404) so callers cannot probe other tenants' rosters.
"""

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


def _make_user(**overrides) -> User:
    from datetime import UTC, datetime

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


def _service_with_target(target: User) -> tuple[UserService, Any]:
    repo: Any = UserRepository()
    repo.get_by_id = AsyncMock(return_value=target)
    repo.role_name_map = AsyncMock(return_value={})
    return UserService(repository=repo), repo


def _admin() -> User:
    # Caller belongs to org-1; targets below use foreign orgs to trip the guard.
    return _make_user(id="admin-1", email="admin@crm.com", organization_id="org-1")


@pytest.mark.asyncio
async def test_get_user_allows_same_org():
    service, _ = _service_with_target(_make_user())
    result = await service.get_user(AsyncMock(spec=AsyncSession), "user-1", current_user=_admin())
    assert result["email"] == "alex@crm.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda s, db, admin: s.get_user(db, "user-1", current_user=admin),
        lambda s, db, admin: s.update_user(
            db, "user-1", type("P", (), {"name": None, "role": None})(), current_user=admin
        ),
        lambda s, db, admin: s.delete_user(db, "user-1", current_user=admin),
        lambda s, db, admin: s.activate_user(db, "user-1", current_user=admin),
        lambda s, db, admin: s.deactivate_user(db, "user-1", current_user=admin),
        lambda s, db, admin: s.get_user_activities(db, "user-1", current_user=admin),
        lambda s, db, admin: s.get_user_teams(db, "user-1", current_user=admin),
        lambda s, db, admin: s.assign_user_team(
            db, user_id="user-1", team_id="t1", team_name=None, current_user=admin
        ),
        lambda s, db, admin: s.remove_user_team(
            db, user_id="user-1", team_id="t1", current_user=admin
        ),
        lambda s, db, admin: s.get_user_effective_permissions(db, "user-1", current_user=admin),
        lambda s, db, admin: s.admin_reset_user_password(db, "user-1", current_user=admin),
        lambda s, db, admin: s.get_user_scorecard(db, "user-1", current_user=admin),
    ],
)
async def test_every_user_endpoint_rejects_cross_org_with_404(call):
    target = _make_user(organization_id="org-other")
    service, repo = _service_with_target(target)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await call(service, db, _admin())


@pytest.mark.asyncio
async def test_delete_user_cross_org_never_deletes():
    target = _make_user(organization_id="org-other")
    service, repo = _service_with_target(target)
    repo.delete = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.delete_user(db, "user-1", current_user=_admin())
    repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_delete_skips_foreign_org_ids():
    same_org = _make_user(id="u-same", email="same@crm.com")
    foreign = _make_user(id="u-foreign", email="foreign@crm.com", organization_id="org-other")
    protected = _make_user(id="u-super", email="superadmin@gmail.com")

    repo: Any = UserRepository()
    repo.list_by_ids = AsyncMock(return_value=[same_org, foreign, protected])
    repo.delete = AsyncMock()
    service = UserService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete_users(
        db, ["u-same", "u-foreign", "u-super"], current_user=_admin()
    )

    # Foreign-org id silently ignored; protected superadmin filtered as before.
    deleted_ids = [call.args[1].id for call in repo.delete.await_args_list]
    assert deleted_ids == ["u-same"]
    assert result["affected_count"] == 1


@pytest.mark.asyncio
async def test_scorecard_allows_same_org():
    service, _ = _service_with_target(_make_user())
    result = await service.get_user_scorecard(
        AsyncMock(spec=AsyncSession), "user-1", current_user=_admin()
    )
    assert result["user_id"] == "user-1"


def _active_org(org_id: str):
    from types import SimpleNamespace

    return SimpleNamespace(id=org_id, status="active", is_active=True)


def _org_scoped_service(list_result):
    """Service whose repo returns `list_result` for org-scoped list calls and
    records the organization_id filter it received."""

    repo: Any = UserRepository()
    seen = {}

    async def fake_list(db, **kwargs):
        seen.update(kwargs)
        return [u for u in list_result if u.organization_id == kwargs["organization_id"]]

    repo.list = fake_list

    async def fake_list_invitations(db, **kwargs):
        seen.update(kwargs)
        return [i for i in list_result if i.organization_id == kwargs["organization_id"]]

    repo.list_invitations = fake_list_invitations
    repo.role_name_map = AsyncMock(return_value={})
    service = UserService(repository=repo)
    cast(Any, service.organization_repository).get_by_id = AsyncMock(
        return_value=_active_org("org-1")
    )
    return service, seen


@pytest.mark.asyncio
async def test_list_users_is_org_scoped_and_pagination_preserved():

    same1 = _make_user(id="u1")
    same2 = _make_user(id="u2", email="bob@crm.com")
    foreign = _make_user(id="u3", email="eve@evil.com", organization_id="org-other")

    service, seen = _org_scoped_service([same1, same2, foreign])

    result = await service.list_users(
        AsyncMock(spec=AsyncSession), page=1, limit=50, search=None, current_user=_admin()
    )

    # Repository was called with the CALLER's org id, pagination intact.
    assert seen["organization_id"] == "org-1"
    assert seen["page"] == 1 and seen["limit"] == 50
    # Foreign-org user is never returned.
    ids = [u["id"] for u in result]
    assert ids == ["u1", "u2"]
    assert all(u["organization_id"] == "org-1" for u in result)


@pytest.mark.asyncio
async def test_list_users_search_remains_org_scoped():
    same = _make_user(id="u1", name="Zeta")
    foreign_match = _make_user(id="u9", name="Zeta9", organization_id="org-other")
    service, seen = _org_scoped_service([same, foreign_match])
    # Simulate the repository applying search AFTER org filter.
    repo_list_original = service.repository.list

    async def searched(db, *, page, limit, search, organization_id):
        rows = await repo_list_original(
            db, page=page, limit=limit, search=search, organization_id=organization_id
        )
        return [r for r in rows if search.lower() in r.name.lower()]

    cast(Any, service.repository).list = searched

    result = await service.list_users(
        AsyncMock(spec=AsyncSession),
        page=1,
        limit=20,
        search="zeta",
        current_user=_admin(),
    )

    assert seen["organization_id"] == "org-1"
    assert [u["id"] for u in result] == ["u1"]


@pytest.mark.asyncio
async def test_list_invitations_is_org_scoped():
    from types import SimpleNamespace

    same = SimpleNamespace(
        id="inv-1",
        email="a@crm.com",
        role="Sales Executive",
        status="pending",
        organization_id="org-1",
        created_at=None,
    )
    foreign = SimpleNamespace(
        id="inv-2",
        email="secret@other.com",
        role="Sales Executive",
        status="pending",
        organization_id="org-other",
        created_at=None,
    )

    service, seen = _org_scoped_service([same, foreign])
    cast(Any, service.repository).role_name_map = AsyncMock(
        return_value={"Sales Executive": "Sales Executive"}
    )

    result = await service.list_user_invitations(
        AsyncMock(spec=AsyncSession),
        token=None,
        status_filter=None,
        current_user=_admin(),
    )

    assert seen["organization_id"] == "org-1"
    emails = [inv["email"] for inv in result]
    assert emails == ["a@crm.com"]
    assert not any("other.com" in e for e in emails)


@pytest.mark.asyncio
async def test_same_org_mutations_still_work_after_guard():
    """Constraint 5: existing same-organization behavior is preserved."""
    target = _make_user()
    service, repo = _service_with_target(target)
    repo.delete = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.deactivate_user(db, "user-1", current_user=_admin())
    assert target.is_active is False
