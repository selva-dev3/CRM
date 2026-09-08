import os

import pytest

from app.tests.run_isolated_workflow import main


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://localhost/production",
    "postgresql+asyncpg://remote.example/crm_workflow_test",
    "sqlite:///crm_workflow_test",
])
def test_workflow_runner_rejects_nonisolated_database_before_clearing_environment(monkeypatch, url):
    monkeypatch.setenv("CRM_WORKFLOW_TEST_DATABASE_URL", url)
    monkeypatch.setenv("RBAC_TEST_SENTINEL", "preserved")
    with pytest.raises(ValueError, match="dedicated localhost"):
        main()
    assert os.environ["RBAC_TEST_SENTINEL"] == "preserved"
