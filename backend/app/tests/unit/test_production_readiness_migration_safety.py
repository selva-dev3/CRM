import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

MIGRATIONS = Path(__file__).resolve().parents[3] / "alembic" / "versions"


def _load_migration(filename: str):
    path = MIGRATIONS / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(*, scalar=None, rows=()):
    result = MagicMock()
    result.scalar_one.return_value = scalar
    result.scalars.return_value.all.return_value = list(rows)
    return result


def test_communication_scope_downgrade_deletes_only_migration_owned_rows(monkeypatch):
    migration = _load_migration(
        "f3b5d7e9a1c2_connect_meetings_calendar_and_communication_owners.py"
    )
    connection = MagicMock()
    connection.execute.side_effect = [
        _result(scalar=False),
        _result(rows=("role-1",)),
        _result(),
    ]
    operations = MagicMock()
    operations.get_bind.return_value = connection
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    statement, params = connection.execute.call_args_list[2].args
    assert "WHERE id = ANY(:ids)" in str(statement)
    assert set(params["ids"]) == {
        migration._stable_id("role-1", module) for module in migration.MODULES
    }
    assert params["modules"] == list(migration.MODULES)


def test_communication_business_data_blocks_destructive_downgrade(monkeypatch):
    migration = _load_migration(
        "f3b5d7e9a1c2_connect_meetings_calendar_and_communication_owners.py"
    )
    connection = MagicMock()
    connection.execute.return_value = _result(scalar=True)
    operations = MagicMock()
    operations.get_bind.return_value = connection
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match="communication ownership/calendar linkage"):
        migration.downgrade()

    operations.drop_column.assert_not_called()


def test_knowledge_scope_downgrade_deletes_only_migration_owned_rows(monkeypatch):
    migration = _load_migration("j7f9b1d3e5a6_scope_knowledge_articles.py")
    connection = MagicMock()
    connection.execute.side_effect = [_result(rows=("role-1", "role-2")), _result()]
    operations = MagicMock()
    operations.get_bind.return_value = connection
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    statement, params = connection.execute.call_args_list[1].args
    assert "id = ANY(:ids)" in str(statement)
    assert params["ids"] == [
        migration._stable_id("role-1"),
        migration._stable_id("role-2"),
    ]


@pytest.mark.parametrize(
    ("filename", "error", "expected_drop"),
    (
        (
            "g4c6e8f0b2d3_add_project_members_and_task_dependencies.py",
            "project membership/dependencies",
            "drop_table",
        ),
        (
            "h5d7f9a1c3e4_add_ticket_escalation_and_documents.py",
            "ticket escalation/documents",
            "drop_column",
        ),
    ),
)
def test_business_data_blocks_destructive_downgrade(monkeypatch, filename, error, expected_drop):
    migration = _load_migration(filename)
    connection = MagicMock()
    connection.execute.return_value = _result(scalar=True)
    operations = MagicMock()
    operations.get_bind.return_value = connection
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match=error):
        migration.downgrade()

    getattr(operations, expected_drop).assert_not_called()


@pytest.mark.parametrize(
    ("filename", "expected_drop"),
    (
        (
            "g4c6e8f0b2d3_add_project_members_and_task_dependencies.py",
            "drop_table",
        ),
        (
            "h5d7f9a1c3e4_add_ticket_escalation_and_documents.py",
            "drop_column",
        ),
    ),
)
def test_empty_feature_data_allows_schema_downgrade(monkeypatch, filename, expected_drop):
    migration = _load_migration(filename)
    connection = MagicMock()
    connection.execute.return_value = _result(scalar=False)
    operations = MagicMock()
    operations.get_bind.return_value = connection
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    assert getattr(operations, expected_drop).called
