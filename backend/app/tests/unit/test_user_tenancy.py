"""Cross-organization tenancy tests for every user-by-id endpoint.

Guards the IDOR fix: any authenticated user may only read/mutate users
belonging to their own organization; foreign-org ids must behave exactly
like missing ones (404) so callers cannot probe other tenants' rosters.
"""

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


def _service_with_target(target: User) -> tuple[UserService, UserRepository]:
    repo = UserRepository()
    repo.get_by_id = AsyncMock(return_value=target)
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

    repo = UserRepository()
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
async def test_same_org_mutations_still_work_after_guard():
    """Constraint 5: existing same-organization behavior is preserved."""
    target = _make_user()
    service, repo = _service_with_target(target)
    repo.delete = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    await service.deactivate_user(db, "user-1", current_user=_admin())
    assert target.is_active is False
