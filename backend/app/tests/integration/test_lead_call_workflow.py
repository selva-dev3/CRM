"""Lead call workflow tests against the isolated migrated PostgreSQL database."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import NotFoundError
from app.models import CallLog, Contact, Lead, Organization, User
from app.schemas.crm_schemas import CallLogBase, CallLogUpdate
from app.services.call_service import CallService
from app.services.lead_service import LeadService


@pytest_asyncio.fixture
async def lead_call_database():
    database_url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(database_url)
    if parsed.host not in {"127.0.0.1", "localhost"} or parsed.database != "crm_workflow_test":
        pytest.fail("Use the dedicated localhost crm_workflow_test database")

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    org = Organization(id=str(uuid4()), name=f"Call workflow tenant {uuid4()}", currency="INR")
    foreign_org = Organization(
        id=str(uuid4()), name=f"Foreign call workflow tenant {uuid4()}", currency="INR"
    )
    user = User(
        id=str(uuid4()),
        organization_id=org.id,
        name="Call workflow user",
        email=f"{uuid4()}@example.com",
        hashed_password=uuid4().hex,
        is_active=True,
    )
    lead = Lead(
        id=str(uuid4()),
        organization_id=org.id,
        title="Call workflow lead",
        company="Example company",
        contact_name="Example buyer",
        email=f"{uuid4()}@example.com",
    )
    contact = Contact(
        id=str(uuid4()),
        organization_id=org.id,
        name="Example buyer",
        email=f"{uuid4()}@example.com",
    )
    foreign_contact = Contact(
        id=str(uuid4()),
        organization_id=foreign_org.id,
        name="Foreign buyer",
        email=f"{uuid4()}@example.com",
    )
    async with sessions() as db:
        db.add_all([org, foreign_org])
        await db.flush()
        db.add_all([user, lead, contact, foreign_contact])
        await db.commit()
    try:
        yield sessions, org, user, lead, contact, foreign_contact
    finally:
        async with sessions() as db:
            await db.execute(delete(Organization).where(Organization.id.in_([org.id, foreign_org.id])))
            await db.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_lead_call_create_retry_timeline_update_delete(
    lead_call_database, monkeypatch
):
    sessions, org, user, lead, contact, _ = lead_call_database
    payload = CallLogBase(
        lead_id=lead.id,
        contact_id=contact.id,
        call_type="Outbound",
        disposition="Completed",
        timestamp=datetime(2026, 9, 8, 10, 30, tzinfo=UTC),
        duration_seconds=125,
        subject="Discovery call",
        notes="Discussed requirements",
    )

    async with sessions() as db:
        created = await CallService().log_call(
            db, payload, user, idempotency_key="lead-call-workflow-request"
        )
        retried = await CallService().log_call(
            db, payload, user, idempotency_key="lead-call-workflow-request"
        )
        assert retried["id"] == created["id"]
        assert retried["created_by"] == user.id
        assert retried["lead_id"] == lead.id
        assert retried["contact_id"] == contact.id

        async def permissions(*_args, **_kwargs):
            return ["calls:read"]

        monkeypatch.setattr(
            "app.services.lead_service.auth_service.get_user_permissions", permissions
        )
        timeline = await LeadService().get_timeline(
            db, lead.id, organization_id=org.id, current_user=user
        )
        call_event = next(event for event in timeline if event["id"] == f"call-{created['id']}")
        assert call_event["title"] == "Discovery call"
        assert "Discussed requirements" in call_event["description"]
        assert "Direction: Outbound" in call_event["description"]

        other_lead = Lead(
            id=str(uuid4()),
            organization_id=org.id,
            title="Other lead",
            company="Other company",
            contact_name="Other buyer",
            email=f"{uuid4()}@example.com",
        )
        db.add(other_lead)
        await db.commit()
        await CallService().update_call(
            db,
            created["id"],
            CallLogUpdate(notes=f"Mentioned [Lead:{other_lead.id}] in free text"),
            user,
        )
        other_timeline = await LeadService().get_timeline(
            db, other_lead.id, organization_id=org.id, current_user=user
        )
        assert all(event["id"] != f"call-{created['id']}" for event in other_timeline)

        updated = await CallService().update_call(
            db,
            created["id"],
            CallLogUpdate(disposition="No Answer", notes="Will retry tomorrow"),
            user,
        )
        assert updated["disposition"] == "No Answer"
        assert updated["notes"] == "Will retry tomorrow"

        await CallService().delete_call(db, created["id"], user)
        assert await db.scalar(select(CallLog).where(CallLog.id == created["id"])) is None


@pytest.mark.asyncio
async def test_lead_call_rejects_foreign_contact(lead_call_database):
    sessions, _, user, lead, _, foreign_contact = lead_call_database
    async with sessions() as db:
        with pytest.raises(NotFoundError):
            await CallService().log_call(
                db,
                CallLogBase(lead_id=lead.id, contact_id=foreign_contact.id),
                user,
            )
        assert await db.scalar(select(CallLog).where(CallLog.lead_id == lead.id)) is None


@pytest.mark.asyncio
async def test_http_lead_call_workflow_enforces_schema_permission_and_idempotency(
    lead_call_database, monkeypatch
):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.deps import get_current_user
    from app.api.v1.routers.calls import router as calls_router
    from app.api.v1.routers.leads import router as leads_router
    from app.core.errors import register_exception_handlers
    from app.db.session import get_db

    sessions, _, user, lead, contact, _ = lead_call_database
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(leads_router, prefix="/api/v1/leads")
    app.include_router(calls_router, prefix="/api/v1/calls")

    async def database_override():
        async with sessions() as db:
            yield db

    granted_permissions = ["calls:read", "calls:create", "calls:update", "calls:delete"]

    async def permissions(*_args, **_kwargs):
        return granted_permissions

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr("app.services.auth_service.auth_service.get_user_permissions", permissions)

    request = {
        "contact_id": contact.id,
        "call_type": "Inbound",
        "disposition": "Completed",
        "duration_seconds": 75,
        "subject": "HTTP workflow call",
    }
    endpoint = f"/api/v1/leads/{lead.id}/calls"
    headers = {"Idempotency-Key": "http-lead-call-workflow"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post(endpoint, json={**request, "duration_seconds": "75"})
        assert invalid.status_code == 422

        granted_permissions.remove("calls:create")
        forbidden = await client.post(
            endpoint,
            json=request,
            headers={"Idempotency-Key": "forbidden-http-lead-call-workflow"},
        )
        assert forbidden.status_code == 403
        granted_permissions.append("calls:create")

        created = await client.post(endpoint, json=request, headers=headers)
        assert created.status_code == 201
        retried = await client.post(endpoint, json=request, headers=headers)
        assert retried.status_code == 201
        assert retried.json()["id"] == created.json()["id"]

        listed = await client.get(endpoint)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [created.json()["id"]]

        updated = await client.put(
            f"/api/v1/calls/{created.json()['id']}",
            json={"notes": "Updated through HTTP"},
        )
        assert updated.status_code == 200
        assert updated.json()["notes"] == "Updated through HTTP"

        deleted = await client.delete(f"/api/v1/calls/{created.json()['id']}")
        assert deleted.status_code == 200
        assert (await client.get(endpoint)).json() == []
