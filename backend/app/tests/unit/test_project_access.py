from app.core.record_access import RecordAccessContext
from app.repositories.project_access import project_record_access_filter


def _context(scope: str) -> RecordAccessContext:
    return RecordAccessContext(
        scope=scope,
        user_id="user-1",
        team_ids=frozenset({"team-1"}),
        team_user_ids=frozenset({"user-1", "user-2"}),
    )


def test_assigned_project_access_includes_project_task_assignment():
    sql = str(project_record_access_filter(_context("assigned")))

    assert "projects.owner_id" in sql
    assert "tasks.project_id = projects.id" in sql
    assert "tasks.assigned_to" in sql


def test_team_project_access_includes_team_task_assignees():
    sql = str(project_record_access_filter(_context("team")))

    assert "projects.owner_id" in sql
    assert "tasks.assigned_to" in sql
