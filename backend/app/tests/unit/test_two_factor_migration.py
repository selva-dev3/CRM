import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import sqlalchemy as sa


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "a7b8c9d0e1f2_add_two_factor_columns_to_users.py"
    )
    spec = importlib.util.spec_from_file_location("two_factor_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeInspector:
    def __init__(self, columns):
        self.columns = columns

    def get_columns(self, table_name):
        assert table_name == "users"
        return self.columns


def _operations(bind):
    return SimpleNamespace(
        get_bind=MagicMock(return_value=bind),
        add_column=MagicMock(),
        drop_column=MagicMock(),
    )


def test_upgrade_adds_missing_2fa_columns_with_expected_schema(monkeypatch):
    migration = _load_migration()
    operations = _operations(object())
    monkeypatch.setattr(migration, "inspect", lambda _: FakeInspector([]))
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    assert [call.args[0] for call in operations.add_column.call_args_list] == ["users", "users"]
    secret_column = operations.add_column.call_args_list[0].args[1]
    enabled_column = operations.add_column.call_args_list[1].args[1]
    assert secret_column.name == "two_factor_secret"
    assert isinstance(secret_column.type, sa.String)
    assert secret_column.type.length == 512
    assert secret_column.nullable is True
    assert enabled_column.name == "two_factor_enabled"
    assert isinstance(enabled_column.type, sa.Boolean)
    assert enabled_column.nullable is False
    assert str(enabled_column.server_default.arg) == "false"


def test_upgrade_is_idempotent_when_2fa_columns_already_exist(monkeypatch):
    migration = _load_migration()
    operations = _operations(object())
    monkeypatch.setattr(
        migration,
        "inspect",
        lambda _: FakeInspector([{"name": "two_factor_secret"}, {"name": "two_factor_enabled"}]),
    )
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    operations.add_column.assert_not_called()


def test_downgrade_removes_existing_2fa_columns(monkeypatch):
    migration = _load_migration()
    operations = _operations(object())
    monkeypatch.setattr(
        migration,
        "inspect",
        lambda _: FakeInspector([{"name": "two_factor_secret"}, {"name": "two_factor_enabled"}]),
    )
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    assert [call.args for call in operations.drop_column.call_args_list] == [
        ("users", "two_factor_enabled"),
        ("users", "two_factor_secret"),
    ]
