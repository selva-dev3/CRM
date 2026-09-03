import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "7fcd8359c9f2_register_all_models.py"
    )
    spec = importlib.util.spec_from_file_location("initial_schema_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_initial_revision_bootstraps_tables_required_by_later_migrations():
    migration = _load_migration()
    statements = "\n".join(migration._BASELINE_DDL)

    assert "CREATE TABLE IF NOT EXISTS organizations" in statements
    assert "CREATE TABLE IF NOT EXISTS users" in statements
    assert "CREATE TABLE IF NOT EXISTS leads" in statements
    leads_statement = next(
        statement
        for statement in migration._BASELINE_DDL
        if "CREATE TABLE IF NOT EXISTS leads" in statement
    )
    assert "website VARCHAR(255)" not in leads_statement
    assert "two_factor_secret" not in statements


def test_upgrade_executes_the_complete_baseline(monkeypatch):
    migration = _load_migration()
    execute = MagicMock()
    monkeypatch.setattr(migration, "op", SimpleNamespace(execute=execute))

    migration.upgrade()

    assert execute.call_count == len(migration._BASELINE_DDL)
    assert execute.call_args_list[0].args[0].startswith("CREATE TABLE IF NOT EXISTS")
