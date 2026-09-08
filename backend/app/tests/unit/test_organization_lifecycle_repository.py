from unittest.mock import AsyncMock

import pytest

from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository


@pytest.mark.asyncio
async def test_delete_dependencies_removes_user_role_mappings_before_role_cascade():
    db = AsyncMock()

    await OrganizationLifecycleRepository().delete_dependencies(db, "org-1")

    statements = [str(call.args[0]) for call in db.execute.await_args_list]
    assert statements[0].startswith("DELETE FROM user_roles")


@pytest.mark.asyncio
async def test_legacy_invitation_acceptance_locks_email_then_tenant_then_invitation(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.repositories.auth_repository import AuthRepository

    events = []
    candidate = SimpleNamespace(email=" Invited@example.com ", organization_id="org-1")
    db = AsyncMock()
    db.scalar.return_value = candidate

    async def lock_email(db, email):
        events.append(("email", email))

    async def lock_org(db, organization_id):
        events.append(("organization", organization_id))

    async def execute(statement):
        events.append(("invitation", "FOR UPDATE" in str(statement)))
        assert statement.get_execution_options()["populate_existing"] is True
        result = MagicMock()
        result.scalars.return_value.first.return_value = candidate
        return result

    monkeypatch.setattr(OrganizationLifecycleRepository, "lock_invitation_email", staticmethod(lock_email))
    monkeypatch.setattr(OrganizationLifecycleRepository, "lock_invitation_organization", staticmethod(lock_org))
    db.execute.side_effect = execute
    assert await AuthRepository().get_invitation_by_token(db, "invitation-test", for_update=True) is candidate
    assert events == [("email", "invited@example.com"), ("organization", "org-1"), ("invitation", True)]
