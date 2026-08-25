import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "c6d7e8f9a0b1_make_quote_deal_nullable.py"
    )
    spec = importlib.util.spec_from_file_location("quote_deal_nullable_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeInspector:
    def __init__(self, *, columns, foreign_keys=None, indexes=None, has_quotes=True):
        self.columns = columns
        self.foreign_keys = foreign_keys or []
        self.indexes = indexes or []
        self.has_quotes = has_quotes

    def get_table_names(self):
        return ["quotes", "deals"] if self.has_quotes else ["deals"]

    def get_columns(self, table_name):
        assert table_name == "quotes"
        return self.columns

    def get_foreign_keys(self, table_name):
        assert table_name == "quotes"
        return self.foreign_keys

    def get_indexes(self, table_name):
        assert table_name == "quotes"
        return self.indexes


def _operations(bind):
    return SimpleNamespace(
        get_bind=MagicMock(return_value=bind),
        add_column=MagicMock(),
        alter_column=MagicMock(),
        drop_constraint=MagicMock(),
        create_foreign_key=MagicMock(),
        create_index=MagicMock(),
    )


def _bind(first=None):
    result = SimpleNamespace(first=MagicMock(return_value=first))
    return SimpleNamespace(execute=MagicMock(return_value=result))


def test_upgrade_repairs_nullability_fk_and_index(monkeypatch):
    migration = _load_migration()
    inspector = FakeInspector(
        columns=[{"name": "deal_id", "nullable": False, "type": sa.String()}],
        foreign_keys=[
            {
                "name": "quotes_deal_id_fkey",
                "constrained_columns": ["deal_id"],
                "referred_table": "deals",
                "referred_columns": ["id"],
                "options": {"ondelete": "RESTRICT"},
            }
        ],
    )
    bind = _bind()
    operations = _operations(bind)
    monkeypatch.setattr(migration, "inspect", lambda _: inspector)
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    operations.alter_column.assert_called_once_with(
        "quotes", "deal_id", existing_type=inspector.columns[0]["type"], nullable=True
    )
    operations.drop_constraint.assert_called_once_with(
        "quotes_deal_id_fkey", "quotes", type_="foreignkey"
    )
    operations.create_foreign_key.assert_called_once_with(
        "fk_quotes_deal_id_deals",
        "quotes",
        "deals",
        ["deal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    operations.create_index.assert_called_once_with(
        "ix_quotes_deal_id", "quotes", ["deal_id"], unique=False
    )


def test_upgrade_adds_missing_nullable_column_without_backfill(monkeypatch):
    migration = _load_migration()
    inspector = FakeInspector(columns=[{"name": "id", "nullable": False, "type": sa.String()}])
    bind = _bind()
    operations = _operations(bind)
    monkeypatch.setattr(migration, "inspect", lambda _: inspector)
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    added_column = operations.add_column.call_args.args[1]
    assert added_column.name == "deal_id"
    assert added_column.nullable is True
    operations.alter_column.assert_not_called()
    operations.create_foreign_key.assert_called_once()
    operations.create_index.assert_called_once()


def test_upgrade_is_noop_for_aligned_schema_with_legacy_nulls(monkeypatch):
    migration = _load_migration()
    inspector = FakeInspector(
        columns=[{"name": "deal_id", "nullable": True, "type": sa.String()}],
        foreign_keys=[
            {
                "name": "quotes_deal_id_fkey",
                "constrained_columns": ["deal_id"],
                "referred_table": "deals",
                "referred_columns": ["id"],
                "options": {"ondelete": "SET NULL"},
            }
        ],
        indexes=[{"name": "ix_quotes_deal_id", "column_names": ["deal_id"]}],
    )
    bind = _bind()
    operations = _operations(bind)
    monkeypatch.setattr(migration, "inspect", lambda _: inspector)
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    operations.add_column.assert_not_called()
    operations.alter_column.assert_not_called()
    operations.drop_constraint.assert_not_called()
    operations.create_foreign_key.assert_not_called()
    operations.create_index.assert_not_called()
    bind.execute.assert_not_called()


def test_upgrade_refuses_to_rewrite_orphaned_quote_relationships(monkeypatch):
    migration = _load_migration()
    inspector = FakeInspector(
        columns=[{"name": "deal_id", "nullable": True, "type": sa.String()}],
        foreign_keys=[
            {
                "name": "quotes_deal_id_fkey",
                "constrained_columns": ["deal_id"],
                "referred_table": "deals",
                "referred_columns": ["id"],
                "options": {},
            }
        ],
    )
    bind = _bind(first=(1,))
    operations = _operations(bind)
    monkeypatch.setattr(migration, "inspect", lambda _: inspector)
    monkeypatch.setattr(migration, "op", operations)

    with pytest.raises(RuntimeError, match="orphaned Deal IDs"):
        migration.upgrade()

    operations.drop_constraint.assert_not_called()
    operations.create_foreign_key.assert_not_called()


def test_downgrade_is_non_destructive(monkeypatch):
    migration = _load_migration()
    warning = MagicMock()
    monkeypatch.setattr(migration.logger, "warning", warning)

    migration.downgrade()

    warning.assert_called_once()
