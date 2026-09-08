"""RBAC hardening migration cases against a disposable local PostgreSQL database."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


@pytest.mark.asyncio
async def test_migration_remaps_exact_ordered_defaults_and_preserves_platform_role(monkeypatch):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set CRM_WORKFLOW_TEST_DATABASE_URL to the isolated local test database")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    database = f"rbac_migration_{uuid4().hex}"
    root = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with root.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    isolated_url = parsed.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(isolated_url)
    monkeypatch.setattr(settings, "DATABASE_URL", isolated_url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    try:
        await asyncio.to_thread(command.upgrade, config, "t4d5e6f7a8b9")
        async with engine.begin() as connection:
            # Historical migrations seed these global templates. Replace them
            # only in this disposable fixture with deterministic IDs below.
            await connection.execute(text(
                "DELETE FROM roles WHERE organization_id IS NULL "
                "AND name IN ('Admin', 'Sales Manager', 'Super Admin')"
            ))
            await connection.execute(
                text(
                    "INSERT INTO organizations (id,name,is_active,status) VALUES "
                    "('org-1','One',true,'active'),('org-2','Two',true,'active')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO roles (id,organization_id,name,is_system_role) VALUES "
                    "('role-1',NULL,'Admin',true),"
                    "('role-10',NULL,'Sales Manager',true),"
                    "('local-admin','org-1','Admin',true),"
                    "('local-manager','org-1','Sales Manager',true),"
                    "('global-super',NULL,'Super Admin',true)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO users "
                    "(id,name,email,hashed_password,role,organization_id,is_platform_admin,is_active,is_verified) "
                    "VALUES ('platform','Platform','platform@example.com','test-hash','Super Admin',NULL,true,true,true)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO user_roles (id,user_id,role_id) "
                    "VALUES ('platform-role','platform','global-super')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO settings (id,key,value) VALUES "
                    "('defaults','default_registration_roles:org-1',"
                    ":default_roles),"
                    "('empty','default_registration_roles:org-2','[]'),"
                    "('single','default_registration_role:org-1','role-10')"
                ),
                {"default_roles": json.dumps([" role-10 ", "role-1", "role-100", None, 7, {"legacy": True}])},
            )

        await asyncio.to_thread(command.upgrade, config, "head")

        async with engine.connect() as connection:
            defaults = await connection.scalar(
                text("SELECT value FROM settings WHERE id='defaults'")
            )
            empty = await connection.scalar(text("SELECT value FROM settings WHERE id='empty'"))
            single = await connection.scalar(text("SELECT value FROM settings WHERE id='single'"))
            platform_role = await connection.scalar(
                text("SELECT role FROM users WHERE id='platform'")
            )
        assert json.loads(defaults) == [
            "local-manager", "local-admin", "role-100", None, 7, {"legacy": True}
        ]
        assert json.loads(empty) == []
        assert single == "local-manager"
        assert platform_role == "Super Admin"

        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users "
                    "(id,name,email,hashed_password,role,organization_id,is_platform_admin,is_active,is_verified) "
                    "VALUES ('racing-user','Racing','racing@example.com','test-hash',"
                    "'local-admin','org-1',false,true,true)"
                )
            )

        first = await engine.connect()
        transaction = await first.begin()
        try:
            await first.execute(
                text("UPDATE users SET organization_id='org-2' WHERE id='racing-user'")
            )

            async def insert_mapping() -> None:
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO user_roles (id,user_id,role_id) "
                            "VALUES ('racing-map','racing-user','local-admin')"
                        )
                    )

            competing = asyncio.create_task(insert_mapping())
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(competing), timeout=0.2)
            await transaction.commit()
            with pytest.raises(DBAPIError):
                await competing
        finally:
            if transaction.is_active:
                await transaction.rollback()
            await first.close()
    finally:
        await engine.dispose()
        async with root.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database}"'))
        await root.dispose()
