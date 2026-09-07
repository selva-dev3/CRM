from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MERGE_REVISION = "e8f9a0b1c2d3"
HEAD_REVISION = "r1a2b3c4d5e6"
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
    ] == ["r1a2b3c4d5e6", "q0f1a2b3c4d5"]
    assert [
        migration.revision for migration in script.iterate_revisions("heads", "o8d9e0f1a2b3")
    ] == ["r1a2b3c4d5e6", "q0f1a2b3c4d5", "p9e0f1a2b3c4"]


def test_merge_revision_joins_ai_and_deal_custom_field_heads():
    revision = _script_directory().get_revision(MERGE_REVISION)

    assert revision is not None
    assert set(revision.down_revision) == EXPECTED_PARENTS
