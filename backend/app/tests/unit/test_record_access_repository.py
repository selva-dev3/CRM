from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.record_access_repository import RecordAccessRepository


@pytest.mark.asyncio
async def test_team_scope_includes_memberships_and_managed_teams():
    result = MagicMock()
    result.all.return_value = ["member-team", "managed-team"]
    db = MagicMock()
    db.scalars = AsyncMock(return_value=result)

    team_ids = await RecordAccessRepository().team_ids_for_user(db, "user-1")

    assert team_ids == frozenset({"member-team", "managed-team"})
    sql = str(db.scalars.await_args.args[0])
    assert "team_memberships.user_id" in sql
    assert "teams.manager_id" in sql


@pytest.mark.asyncio
async def test_team_users_include_members_and_team_manager():
    result = MagicMock()
    result.all.return_value = ["member-1", "manager-1"]
    db = MagicMock()
    db.scalars = AsyncMock(return_value=result)

    user_ids = await RecordAccessRepository().user_ids_for_teams(db, frozenset({"team-1"}))

    assert user_ids == frozenset({"member-1", "manager-1"})
    sql = str(db.scalars.await_args.args[0])
    assert "team_memberships.user_id" in sql
    assert "teams.manager_id" in sql


@pytest.mark.asyncio
async def test_team_users_skip_query_when_user_has_no_teams():
    db = MagicMock()
    db.scalars = AsyncMock()

    assert await RecordAccessRepository().user_ids_for_teams(db, frozenset()) == frozenset()
    db.scalars.assert_not_awaited()
