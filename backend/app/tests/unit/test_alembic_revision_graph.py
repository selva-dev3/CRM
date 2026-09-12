from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import ForeignKey

from app.models import RolePermission, UserRole

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MERGE_REVISION = "e8f9a0b1c2d3"
HEAD_REVISION = "p1r2o3j4s5f6"
CONTACT_EMAIL_HISTORY_REVISION = "z0d1e2f3g4h5"
CONTACT_EMAIL_HISTORY_INDEX_REVISION = "y9c0d1e2f3g4"
CONTACT_CONTEXT_REVISION = "x8b9c0d1e2f3"
PREVIOUS_HEAD_REVISION = "w7a8b9c0d1e2"
WHATSAPP_REVISION = "v6f7a8b9c0d1"
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
        CONTACT_EMAIL_HISTORY_REVISION,
        CONTACT_EMAIL_HISTORY_INDEX_REVISION,
        CONTACT_CONTEXT_REVISION,
        PREVIOUS_HEAD_REVISION,
        WHATSAPP_REVISION,
        "u5e6f7a8b9c0",
        "t4d5e6f7a8b9",
        "s2b3c4d5e6f7",
        "s3c4d5e6f7a8",
        "r1a2b3c4d5e6",
        "q0f1a2b3c4d5",
    ]
    assert [
        migration.revision for migration in script.iterate_revisions("heads", "o8d9e0f1a2b3")
    ] == [
        HEAD_REVISION,
        CONTACT_EMAIL_HISTORY_REVISION,
        CONTACT_EMAIL_HISTORY_INDEX_REVISION,
        CONTACT_CONTEXT_REVISION,
        PREVIOUS_HEAD_REVISION,
        WHATSAPP_REVISION,
        "u5e6f7a8b9c0",
        "t4d5e6f7a8b9",
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


def test_whatsapp_contact_context_follows_provider_migration():
    script = _script_directory()
    email_history_revision = script.get_revision(CONTACT_EMAIL_HISTORY_REVISION)
    index_revision = script.get_revision(CONTACT_EMAIL_HISTORY_INDEX_REVISION)
    context_revision = script.get_revision(CONTACT_CONTEXT_REVISION)

    assert email_history_revision is not None
    assert index_revision is not None
    assert context_revision is not None
    assert email_history_revision.down_revision == CONTACT_EMAIL_HISTORY_INDEX_REVISION
    assert index_revision.down_revision == CONTACT_CONTEXT_REVISION
    assert context_revision.down_revision == PREVIOUS_HEAD_REVISION


def test_whatsapp_contact_indexes_are_created_concurrently():
    source = (
        BACKEND_ROOT
        / "alembic/versions/y9c0d1e2f3g4_whatsapp_contact_context_indexes.py"
    ).read_text()

    assert "autocommit_block" in source
    assert source.count("postgresql_concurrently=True") == 6
    assert source.count("if_not_exists=True") == 3


def test_contact_email_history_indexes_are_non_blocking_without_bulk_backfill():
    source = (
        BACKEND_ROOT
        / "alembic/versions/z0d1e2f3g4h5_contact_email_history.py"
    ).read_text()

    assert "autocommit_block" in source
    assert source.count("CONCURRENTLY") == 4
    assert source.count("postgresql_concurrently=True") == 2
    assert "UPDATE emails" not in source


def test_susanoox_migration_updates_only_active_provider_configuration():
    source = (
        BACKEND_ROOT / "alembic/versions/w7a8b9c0d1e2_migrate_openrouter_to_susanoox.py"
    ).read_text()

    assert "UPDATE ai_organization_configs" in source
    assert "provider = 'susanoox'" in source
    assert "model_name = 'susanoox-fast'" in source
    assert "ai_runs" not in source


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
