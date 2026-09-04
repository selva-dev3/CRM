from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[3]
MERGE_REVISION = "e8f9a0b1c2d3"
EXPECTED_PARENTS = {"d4e5f6a7b8c0", "d6e7f8a9b0c1"}


def _script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_alembic_revision_graph_has_one_head():
    script = _script_directory()

    assert script.get_heads() == [MERGE_REVISION]


def test_merge_revision_joins_ai_and_deal_custom_field_heads():
    revision = _script_directory().get_revision(MERGE_REVISION)

    assert revision is not None
    assert set(revision.down_revision) == EXPECTED_PARENTS
