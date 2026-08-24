from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.workers.tasks import _deliver_due_reports


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)


class _FakeSession:
    def __init__(self, items):
        self.items = items
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        return _FakeResult(self.items)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _schedule(id="s1", email="ops@acme.test", freq="Daily", due=True):

    return type(
        "Sched",
        (),
        {
            "id": id,
            "organization_id": "org-1",
            "report_type": "win-loss-ratio",
            "email": email,
            "frequency": freq,
            "next_run": (
                datetime.now(UTC) - timedelta(hours=1)
                if due
                else datetime.now(UTC) + timedelta(days=1)
            ),
        },
    )()


@pytest.fixture
def patched_infra(monkeypatch):
    """Stub DB session, S3, CSV generation and the Brevo sender."""
    schedules = []
    session = _FakeSession(schedules)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: session)

    sent = {}

    def fake_send_email(to_email, subject, html_content):
        sent["to"] = to_email
        return True

    monkeypatch.setattr("app.services.email_service.send_email", fake_send_email)

    monkeypatch.setattr(
        "app.services.s3_service.s3_service.upload_file", lambda *a, **kw: "exports/k.csv"
    )
    monkeypatch.setattr(
        "app.services.s3_service.s3_service.generate_presigned_url",
        lambda key, expiration_seconds=3600: f"https://s3.example/{key}?exp={expiration_seconds}",
    )

    csv_builder = AsyncMock(return_value='"segment"\n"Software"')
    monkeypatch.setattr(
        "app.services.report_service.report_service.build_report_csv_for_organization",
        csv_builder,
    )

    monkeypatch.setattr("app.core.config.settings.BREVO_API_KEY", "test-key")
    return {"session": session, "schedules": schedules, "sent": sent}


@pytest.mark.asyncio
async def test_successful_delivery_advances_next_run(patched_infra):
    sched = _schedule()
    original_next = sched.next_run
    patched_infra["schedules"].append(sched)

    result = await _deliver_due_reports()

    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert patched_infra["sent"]["to"] == "ops@acme.test"
    # next_run advanced beyond its previous value after real send success.
    assert sched.next_run > original_next
    assert patched_infra["session"].commits == 1


@pytest.mark.asyncio
async def test_failed_delivery_does_not_advance_next_run(patched_infra, monkeypatch):
    sched = _schedule()
    original_next = sched.next_run
    patched_infra["schedules"].append(sched)

    def failing_send(to_email, subject, html_content):
        return False

    monkeypatch.setattr("app.services.email_service.send_email", failing_send)

    result = await _deliver_due_reports()

    assert result["delivered"] == 0
    assert result["failed"] == 1
    # Schedule must stay due so the next sweep retries it.
    assert sched.next_run == original_next
    assert patched_infra["session"].rollbacks >= 1


@pytest.mark.asyncio
async def test_unconfigured_brevo_key_skips_everything(patched_infra, monkeypatch):
    sched = _schedule()
    original_next = sched.next_run
    patched_infra["schedules"].append(sched)
    monkeypatch.setattr("app.core.config.settings.BREVO_API_KEY", None)

    result = await _deliver_due_reports()

    assert result.get("skipped_unconfigured") is True
    # Schedule left untouched for retry once the key is configured.
    assert sched.next_run == original_next
    assert patched_infra["sent"] == {}
