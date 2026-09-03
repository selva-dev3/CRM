import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

REVISION = "c3d4e5f6a7b9"


def _load_migration():
    versions_dir = next(
        parent / "alembic" / "versions"
        for parent in Path(__file__).resolve().parents
        if (parent / "alembic" / "versions").is_dir()
    )
    migration_path = next(versions_dir.glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("super_admin_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "CREATE TABLE roles ("
            "id VARCHAR PRIMARY KEY, organization_id VARCHAR, name VARCHAR NOT NULL, "
            "description VARCHAR, is_system_role BOOLEAN NOT NULL, created_at TIMESTAMP NOT NULL)"
        )
    )
    connection.execute(sa.text("CREATE TABLE users (id VARCHAR PRIMARY KEY, role VARCHAR)"))
    connection.execute(
        sa.text(
            "CREATE TABLE user_roles (id VARCHAR PRIMARY KEY, user_id VARCHAR, role_id VARCHAR)"
        )
    )


def test_upgrade_creates_global_role_and_idempotently_backfills_legacy_user(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _schema(connection)
        connection.execute(sa.text("INSERT INTO users (id, role) VALUES ('user-1', 'super_admin')"))
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        migration.upgrade()
        migration.upgrade()

        role = connection.execute(
            sa.text("SELECT id, name, organization_id, is_system_role FROM roles")
        ).one()
        mappings = connection.execute(sa.text("SELECT user_id, role_id FROM user_roles")).all()

    assert role.name == "Super Admin"
    assert role.organization_id is None
    assert bool(role.is_system_role) is True
    assert mappings == [("user-1", role.id)]


def test_upgrade_stops_when_global_super_admin_roles_are_ambiguous(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _schema(connection)
        connection.execute(
            sa.text(
                "INSERT INTO roles "
                "(id, organization_id, name, is_system_role, created_at) VALUES "
                "('role-1', NULL, 'super_admin', TRUE, CURRENT_TIMESTAMP), "
                "('role-2', NULL, 'Super Admin', TRUE, CURRENT_TIMESTAMP)"
            )
        )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        with pytest.raises(RuntimeError, match="Multiple global Super Admin roles"):
            migration.upgrade()


def test_upgrade_reuses_existing_global_alias_and_marks_it_protected(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _schema(connection)
        connection.execute(
            sa.text(
                "INSERT INTO roles "
                "(id, organization_id, name, is_system_role, created_at) "
                "VALUES ('existing-super', NULL, 'super_admin', FALSE, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            sa.text("INSERT INTO users (id, role) VALUES ('user-1', 'Super Admin')")
        )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        migration.upgrade()

        role = connection.execute(
            sa.text("SELECT id, is_system_role FROM roles")
        ).one()
        mapping = connection.execute(
            sa.text("SELECT user_id, role_id FROM user_roles")
        ).one()

    assert role.id == "existing-super"
    assert bool(role.is_system_role) is True
    assert mapping == ("user-1", "existing-super")


def test_upgrade_does_not_treat_tenant_role_as_platform_super_admin(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _schema(connection)
        connection.execute(
            sa.text(
                "INSERT INTO roles "
                "(id, organization_id, name, is_system_role, created_at) "
                "VALUES ('tenant-super', 'org-1', 'Super Admin', FALSE, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            sa.text("INSERT INTO users (id, role) VALUES ('user-1', 'super_admin')")
        )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        migration.upgrade()

        global_role = connection.execute(
            sa.text("SELECT id FROM roles WHERE organization_id IS NULL")
        ).one()
        mapping = connection.execute(
            sa.text("SELECT user_id, role_id FROM user_roles")
        ).one()

    assert global_role.id != "tenant-super"
    assert mapping == ("user-1", global_role.id)
