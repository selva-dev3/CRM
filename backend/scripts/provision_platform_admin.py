"""Provision the single platform account using a runtime secret or hidden prompt.

Run from backend: python -m scripts.provision_platform_admin --email EMAIL
For an existing account, supply --existing-user-id after reviewing its identity.
DATABASE_URL and application settings must come from the runtime environment.
Never pass the password on the command line. No .env file is loaded.
"""

import argparse
import asyncio
import getpass
import os
import sys


async def provision(email: str, existing_user_id: str | None, password: str) -> str:
    from app.db.session import AsyncSessionLocal, engine
    from app.services.platform_admin_service import PlatformAdminService
    from pydantic import SecretStr

    try:
        async with AsyncSessionLocal() as db:
            return await PlatformAdminService().provision(
                db, email=email, existing_user_id=existing_user_id, password=SecretStr(password)
            )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--existing-user-id")
    args = parser.parse_args()
    os.environ["CRM_DISABLE_DOTENV"] = "1"
    password = os.environ.pop("PLATFORM_ADMIN_INITIAL_PASSWORD", None)
    if password is None:
        if not sys.stdin.isatty():
            sys.stderr.write(
                "Provide PLATFORM_ADMIN_INITIAL_PASSWORD through the runtime secret manager.\n"
            )
            return 1
        password = getpass.getpass("Initial platform password: ")
    try:
        user_id = asyncio.run(provision(args.email, args.existing_user_id, password))
    except Exception:
        # Do not expose connection strings, SQL parameters, or password material.
        sys.stderr.write(
            "Provisioning failed; verify identity conflicts, migration state, and runtime configuration.\n"
        )
        return 1
    sys.stdout.write(f"Platform account provisioned; preserved user ID: {user_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
