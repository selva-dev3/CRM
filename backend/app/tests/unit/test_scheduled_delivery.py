"""Tests for the claim/process/finalize scheduled-report delivery sweep."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.workers import tasks as tasks_module
from app.workers.tasks import _deliver_due_reports


class _FakeResult:
    """Mimics SQLAlchemy Result for .all() / .first() / .rowcount."""

    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Scripted session: pops one _FakeResult per execute() call."""

    def __init__(self, results=None):
        self.results = list(results or [])
        self.commits = 0
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        return self.results.pop(0)

    async def commit(self):
        self.commits += 1


def _row(id="s1", email="ops@acme.test", freq="Daily", due=True):
    return {
        "id": id,
        "organization_id": "org-1",
        "report_type": "win-loss-ratio",
        "email": email,
        "frequency": freq,
        "next_run": (
            datetime.now(UTC) - timedelta(hours=1) if due else datetime.now(UTC) + timedelta(days=1)
        ),
    }


def _install_common_stubs(monkeypatch, infra, fail_send=False):
    """Wire S3/email/CSV stubs used by every delivery scenario."""

    def fake_upload(file_obj, object_name="", content_type=None):
        infra["uploaded"][object_name] = True
        return object_name

    monkeypatch.setattr("app.services.s3_service.s3_service.upload_file", fake_upload)
    monkeypatch.setattr(
        "app.services.s3_service.s3_service.generate_presigned_url",
        lambda key, expiration_seconds=3600: f"https://s3.example/{key}?sig=abc&exp=1",
    )

    def fake_delete(key):
        infra["deleted"][key] = True
        return True

    monkeypatch.setattr(tasks_module, "_delete_object_quietly", fake_delete)

    def fake_send(to_email, subject, html_content):
        if fail_send:
            return False
        infra["sent"]["to"] = to_email
        return True

    monkeypatch.setattr("app.services.email_service.send_email", fake_send)

    csv_builder = AsyncMock(return_value='"segment"\n"Software"')
    monkeypatch.setattr(
        "app.services.report_service.report_service.build_report_csv_for_organization",
        csv_builder,
    )


def _wire_sweep(monkeypatch, phase_a_session, per_schedule_sessions):
    """Phase A returns `phase_a_session`; each subsequent open gets the next
    scripted per-schedule session (cycled when exhausted)."""
    queue = [phase_a_session, *per_schedule_sessions]
    factory = lambda: queue.pop(0) if len(queue) > 1 else queue[-1]  # noqa: E731
    # _deliver_due_reports imports AsyncSessionLocal lazily from its source
    # module, so patch it there.
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", factory)


def _claim_row_tuple(row):
    """RETURNING column order used by _deliver_one:
    id, organization_id, report_type, email, frequency, next_run."""
    return (
        row["id"],
        row["organization_id"],
        row["report_type"],
        row["email"],
        row["frequency"],
        row["next_run"],
    )


@pytest.mark.asyncio
async def test_successful_delivery_advances_next_run_and_clears_claim(
    monkeypatch,
):
    row = _row()

    # Sessions in order: Phase A ids -> Phase B1 claim RETURNING -> Phase C success.
    phase_a = _FakeSession([_FakeResult(rows=[(row["id"],)])])
    claim_sess = _FakeSession([_FakeResult(rows=[_claim_row_tuple(row)], rowcount=1)])
    finalize_sess = _FakeSession([_FakeResult(rowcount=1)])
    _wire_sweep(monkeypatch, phase_a, [claim_sess, finalize_sess])

    _install_common_stubs(monkeypatch, {"sent": {}, "uploaded": {}, "deleted": {}})

    result = await _deliver_due_reports()

    assert result == {"delivered": 1, "failed": 0}
    finalize_stmt = str(finalize_sess.executed[0]).lower()
    # Finalize is conditional on the exact claim token and clears it.
    assert "claimed_until" in finalize_stmt
    assert "next_run" in finalize_stmt
    assert claim_sess.commits == 1 and finalize_sess.commits == 1


@pytest.mark.asyncio
async def test_failed_email_does_not_advance_next_run_releases_claim_and_cleans_orphan(
    monkeypatch,
):
    row = _row()

    phase_a = _FakeSession([_FakeResult(rows=[(row["id"],)])])
    claim_sess = _FakeSession([_FakeResult(rows=[_claim_row_tuple(row)], rowcount=1)])
    release_sess = _FakeSession([_FakeResult(rowcount=1)])
    _wire_sweep(monkeypatch, phase_a, [claim_sess, release_sess])

    infra = {"sent": {}, "uploaded": {}, "deleted": {}}
    _install_common_stubs(monkeypatch, infra, fail_send=True)

    result = await _deliver_due_reports()

    assert result == {"delivered": 0, "failed": 1}
    # Orphan CSV from the failed send was removed.
    assert len(infra["deleted"]) == 1
    # Claim released so the next sweep retries; next_run untouched.
    release_stmt = str(release_sess.executed[0]).lower()
    assert "claimed_until" in release_stmt
    assert "next_run" not in release_stmt


@pytest.mark.asyncio
async def test_claim_taken_elsewhere_is_skipped(monkeypatch):
    row = _row()

    phase_a = _FakeSession([_FakeResult(rows=[(row["id"],)])])
    # Phase B1 UPDATE ... RETURNING matches nothing -> already claimed elsewhere.
    claim_sess = _FakeSession([_FakeResult(rows=[], rowcount=0)])
    _wire_sweep(monkeypatch, phase_a, [claim_sess])

    infra = {"sent": {}, "uploaded": {}, "deleted": {}}
    _install_common_stubs(monkeypatch, infra)

    result = await _deliver_due_reports()
    assert result == {"delivered": 0, "failed": 0}
    # No email attempted and no object uploaded.
    assert not infra["sent"] and not infra["uploaded"]


@pytest.mark.asyncio
async def test_finalize_guard_zero_rowcount_does_not_crash(monkeypatch):
    """If another worker re-claimed between send and finalize, the guarded
    update matches 0 rows; the sweep must log and continue, not overwrite."""
    row = _row()

    phase_a = _FakeSession([_FakeResult(rows=[(row["id"],)])])
    claim_sess = _FakeSession([_FakeResult(rows=[_claim_row_tuple(row)], rowcount=1)])
    finalize_sess = _FakeSession([_FakeResult(rowcount=0)])
    _wire_sweep(monkeypatch, phase_a, [claim_sess, finalize_sess])

    _install_common_stubs(monkeypatch, {"sent": {}, "uploaded": {}, "deleted": {}})

    result = await _deliver_due_reports()
    assert result["delivered"] == 1


@pytest.mark.asyncio
async def test_unconfigured_brevo_key_skips_everything(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.BREVO_API_KEY", None)
    result = await _deliver_due_reports()
    assert result.get("skipped_unconfigured") is True


@pytest.mark.asyncio
async def test_html_body_escapes_presigned_url(monkeypatch):
    row = _row()

    phase_a = _FakeSession([_FakeResult(rows=[(row["id"],)])])
    claim_sess = _FakeSession([_FakeResult(rows=[_claim_row_tuple(row)], rowcount=1)])
    finalize_sess = _FakeSession([_FakeResult(rowcount=1)])
    _wire_sweep(monkeypatch, phase_a, [claim_sess, finalize_sess])

    captured = {}

    def fake_send(to_email, subject, html_content):
        captured["html"] = html_content
        return True

    monkeypatch.setattr("app.services.email_service.send_email", fake_send)
    monkeypatch.setattr(
        "app.services.s3_service.s3_service.upload_file",
        lambda *a, **kw: "exports/k.csv",
    )
    monkeypatch.setattr(
        "app.services.s3_service.s3_service.generate_presigned_url",
        lambda key, expiration_seconds=3600: f"https://s3.example/{key}?X-Amz-Signature=a&b=c",
    )
    monkeypatch.setattr(
        "app.services.report_service.report_service.build_report_csv_for_organization",
        AsyncMock(return_value="csv"),
    )

    await _deliver_due_reports()
    # Raw '&' must be escaped inside the href attribute.
    assert "&amp;" in captured["html"]
