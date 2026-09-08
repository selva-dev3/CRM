from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import ForeignKey

from app.models import RolePermission, UserRole

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MERGE_REVISION = "e8f9a0b1c2d3"
HEAD_REVISION = "u5e6f7a8b9c0"
PREVIOUS_HEAD_REVISION = "t4d5e6f7a8b9"
EXPECTED_PARENTS = {"d4e5f6a7b8c0", "d6e7f8a9b0c1"}


def _script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_alembic_revision_graph_has_one_head():
    script = _script_directory()

    assert script.get_heads() == [HEAD_REVISION]


def test_rbac_revision_resolves_existing_database_stamp():
    script = _script_directory()
    revision = script.get_revision("p9e0f1a2b3c4")

    assert revision is not None
    assert revision.down_revision == "o8d9e0f1a2b3"
    assert [
        migration.revision
        for migration in script.iterate_revisions("heads", "p9e0f1a2b3c4")
    ] == [
        HEAD_REVISION,
        PREVIOUS_HEAD_REVISION,
        "s2b3c4d5e6f7",
        "s3c4d5e6f7a8",
        "r1a2b3c4d5e6",
        "q0f1a2b3c4d5",
    ]
    assert [
        migration.revision for migration in script.iterate_revisions("heads", "o8d9e0f1a2b3")
    ] == [
        HEAD_REVISION,
        PREVIOUS_HEAD_REVISION,
        "s2b3c4d5e6f7",
        "s3c4d5e6f7a8",
        "r1a2b3c4d5e6",
        "q0f1a2b3c4d5",
        "p9e0f1a2b3c4",
    ]


def test_merge_revision_joins_ai_and_deal_custom_field_heads():
    revision = _script_directory().get_revision(MERGE_REVISION)

    assert revision is not None
    assert set(revision.down_revision) == EXPECTED_PARENTS


def test_rbac_migration_normalizes_catalog_and_remaps_all_legacy_role_references():
    source = (
        BACKEND_ROOT / "alembic/versions/u5e6f7a8b9c0_harden_rbac_integrity.py"
    ).read_text()

    assert "SET key = approved.key" in source
    assert "lower(btrim(permission.key)) = approved.key" in source
    assert "UPDATE user_invitations invitation" in source
    assert "UPDATE organization_invitations invitation" in source
    assert "UPDATE settings setting" in source
    assert "unresolved user invitation roles" in source
    assert "unresolved organization invitation roles" in source
    assert "unresolved default role settings" in source
    assert "SET role = ur.role_id" in source
    assert "trg_user_scope_update" in source
    assert "trg_role_scope_update" in source
    assert "pg_advisory_xact_lock" in source
    assert "WITH ORDINALITY" in source
    assert "'[]'::jsonb" in source
    assert "strpos(setting.value, r.id)" not in source
    assert 'ondelete="RESTRICT"' in source


def test_rbac_models_match_migrated_role_delete_behavior():
    role_permission_fk = next(
        constraint
        for constraint in RolePermission.__table__.c.role_id.foreign_keys
        if isinstance(constraint, ForeignKey)
    )
    user_role_fk = next(
        constraint
        for constraint in UserRole.__table__.c.role_id.foreign_keys
        if isinstance(constraint, ForeignKey)
    )

    assert role_permission_fk.ondelete == "CASCADE"
    assert user_role_fk.ondelete == "RESTRICT"
