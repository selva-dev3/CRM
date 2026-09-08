"""Run from backend with .venv/bin/python -m app.tests.run_isolated_workflow.

Supply --migrate to migrate the disposable DB, otherwise arguments go to pytest.
Only the explicitly named localhost disposable database is used. Dotenv files
are disabled before importing application settings; inherited secrets are cleared.
"""

import asyncio
import importlib
import json
import os
import sys
from importlib.abc import MetaPathFinder
from unittest.mock import patch

from pydantic_settings import DotEnvSettingsSource
from sqlalchemy.engine import make_url


class BlockStripeImports(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "stripe" or fullname.startswith("stripe."):
            raise ModuleNotFoundError("Stripe imports are forbidden in manual billing tests")
        return None


async def verify_startup() -> int:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health")
        assert response.status_code == 200, response.text
        assert response.json() == {"status": "ok", "database": "ok"}
    assert not any(name == "stripe" or name.startswith("stripe.") for name in sys.modules)
    sys.stdout.write(
        json.dumps({"startup": "ok", "health": response.json(), "stripe_imports": "blocked"}) + "\n"
    )
    return 0


def main() -> int:
    database_url = os.environ.get(
        "CRM_WORKFLOW_TEST_DATABASE_URL",
        "postgresql+asyncpg://workflow_test:disposable-test-only@127.0.0.1:55439/crm_workflow_test",
    )
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+asyncpg"
        or parsed.host not in {"localhost", "127.0.0.1"}
        or parsed.database != "crm_workflow_test"
    ):
        raise ValueError("Use the dedicated localhost crm_workflow_test database")
    os.environ.clear()
    os.environ.update(
        {
            "PATH": "/usr/bin:/bin",
            "DATABASE_URL": database_url,
            "SECRET_KEY": "disposable-test-signing-key",
            "AWS_ACCESS_KEY_ID": "disposable-test-only",
            "AWS_SECRET_ACCESS_KEY": "disposable-test-only",
            "AWS_EC2_METADATA_DISABLED": "true",
            "ENVIRONMENT": "test",
            "RATE_LIMIT_STORAGE_URI": "memory://",
        }
    )
    os.environ["CRM_WORKFLOW_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
    patch.object(DotEnvSettingsSource, "_read_env_files", return_value={}).start()
    sys.meta_path.insert(0, BlockStripeImports())
    try:
        importlib.import_module("stripe")
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError("Stripe import blocker is ineffective")
    if sys.argv[1:] == ["--startup"]:
        return asyncio.run(verify_startup())
    if sys.argv[1:] == ["--migrate"]:
        from alembic.config import main as alembic_main

        alembic_main(argv=["upgrade", "head"])
        return 0
    import pytest

    return pytest.main(sys.argv[1:] or ["-q", "app/tests/integration/test_sales_quote_workflow.py"])


if __name__ == "__main__":
    raise SystemExit(main())
