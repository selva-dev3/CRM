import io
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Document, User
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService, document_to_dict


def _make_user(**overrides) -> User:
    defaults = {
        "id": "usr-123",
        "email": "user@crm.com",
        "name": "Alex Smith",
        "organization_id": "org-test",
        "role": "Admin",
        "hashed_password": "hash",
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_document(**overrides) -> Document:
    defaults = {
        "id": "doc-1",
        "organization_id": "org-test",
        "folder_id": None,
        "filename": "proposal.pdf",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "file_url": None,
        "s3_key": "documents/org-test/abcdef.pdf",
        "uploaded_by": "usr-123",
        "uploaded_at": datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Document(**defaults)


def _upload_file(
    content: bytes, filename: str = "1.png", content_type: str = "image/png", size: int = 0
) -> UploadFile:
    headers = Headers({"content-type": content_type})
    f = UploadFile(filename=filename, file=io.BytesIO(content), size=size or None, headers=headers)
    return f


@pytest.mark.asyncio
async def test_list_documents_generates_fresh_presigned_url(monkeypatch):
    repo: Any = DocumentRepository()
    repo.list_documents = AsyncMock(return_value=[_make_document()])
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(organization_id="org-test")

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: f"https://s3.example/{key}?fresh=1",
    )

    result = await service.list_documents(
        db, page=1, limit=20, search="proposal", current_user=user
    )

    repo.list_documents.assert_awaited_once_with(
        db, org_id="org-test", page=1, limit=20, search="proposal"
    )
    assert result[0]["filename"] == "proposal.pdf"
    assert result[0]["mime_type"] == "application/pdf"
    assert result[0]["download_url"].startswith("https://s3.example/documents/org-test/abcdef.pdf")


@pytest.mark.asyncio
async def test_list_documents_legacy_rows_get_empty_download_url(monkeypatch):
    legacy = _make_document(s3_key=None, file_url="https://expired.example/old")
    repo: Any = DocumentRepository()
    repo.list_documents = AsyncMock(return_value=[legacy])
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: (_ for _ in ()).throw(AssertionError("must not be called")),
    )

    result = await service.list_documents(db, page=1, limit=20, current_user=_make_user())
    assert result[0]["download_url"] == ""


@pytest.mark.asyncio
async def test_list_documents_requires_user_with_org():
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError):
        await service.list_documents(db, page=1, limit=20, current_user=None)


@pytest.mark.asyncio
async def test_get_document_not_found():
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=None)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    with pytest.raises(NotFoundError):
        await service.get_document(db, "missing", current_user=user)


@pytest.mark.asyncio
async def test_get_document_generates_fresh_presigned_url(monkeypatch):
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=_make_document())
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: f"https://s3.example/{key}?fresh=1",
    )

    result = await service.get_document(db, "doc-1", current_user=user)
    assert result["download_url"].startswith("https://s3.example/documents/org-test/abcdef.pdf")


@pytest.mark.asyncio
async def test_download_document_generates_fresh_presigned_url(monkeypatch):
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=_make_document())
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: f"https://s3.example/{key}?fresh=1",
    )

    result = await service.download_document(db, "doc-1", current_user=user)
    assert result["download_url"].startswith("https://s3.example/documents/org-test/abcdef.pdf")
    assert result["filename"] == "proposal.pdf"
    assert result["expires_in"] == 3600


@pytest.mark.asyncio
async def test_download_document_raises_410_when_no_s3_key(monkeypatch):
    legacy = _make_document(s3_key=None, file_url="https://expired.example/old")
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=legacy)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: (_ for _ in ()).throw(AssertionError("must not be called")),
    )

    with pytest.raises(APIException) as exc:
        await service.download_document(db, "doc-1", current_user=_make_user())
    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_download_document_raises_502_when_s3_fails(monkeypatch):
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=_make_document())
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr("app.services.document_service.s3_service.generate_presigned_url", boom)

    with pytest.raises(APIException) as exc:
        await service.download_document(db, "doc-1", current_user=_make_user())
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_delete_document_commits_then_cleans_s3(monkeypatch):
    document = _make_document()
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    delete_calls: list[str] = []
    monkeypatch.setattr(
        "app.services.document_service.s3_service.delete_file",
        lambda key: delete_calls.append(key),
    )

    result = await service.delete_document(db, "doc-1", current_user=user)

    repo.delete_document.assert_awaited_once_with(db, document)
    db.commit.assert_awaited_once()
    assert delete_calls == [document.s3_key]
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_delete_document_swallows_post_commit_s3_failure(monkeypatch):
    document = _make_document()
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr("app.services.document_service.s3_service.delete_file", boom)

    result = await service.delete_document(db, "doc-1", current_user=_make_user())
    repo.delete_document.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_bulk_delete_commits_then_cleans_s3(monkeypatch):
    docs = [
        _make_document(id="doc-1"),
        _make_document(id="doc-2", s3_key="documents/org-test/zzz.pdf"),
    ]
    repo: Any = DocumentRepository()
    repo.list_by_ids = AsyncMock(return_value=docs)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    delete_calls: list[str] = []
    monkeypatch.setattr(
        "app.services.document_service.s3_service.delete_file",
        lambda key: delete_calls.append(key),
    )

    result = await service.bulk_delete(db, ["doc-1", "doc-2"], current_user=_make_user())

    assert result["affected_count"] == 2
    db.commit.assert_awaited_once()
    assert delete_calls == ["documents/org-test/abcdef.pdf", "documents/org-test/zzz.pdf"]


@pytest.mark.asyncio
async def test_bulk_delete_swallows_post_commit_s3_failures(monkeypatch):
    docs = [_make_document(id="doc-1"), _make_document(id="doc-2")]
    repo: Any = DocumentRepository()
    repo.list_by_ids = AsyncMock(return_value=docs)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr("app.services.document_service.s3_service.delete_file", boom)

    result = await service.bulk_delete(db, ["doc-1", "doc-2"], current_user=_make_user())
    assert result["affected_count"] == 2
    db.commit.assert_awaited_once()


def test_document_to_dict_uses_fallbacks():
    doc = _make_document(file_size=None, mime_type=None, s3_key=None)
    result = document_to_dict(doc, download_url="")
    assert result["file_size"] == 0
    assert result["mime_type"] == "application/octet-stream"
    assert result["download_url"] == ""


@pytest.mark.asyncio
async def test_upload_document_stores_s3_key_not_presigned_url(monkeypatch):
    repo: Any = DocumentRepository()
    mock_doc = _make_document(
        id="doc-new",
        filename="report.png",
        file_size=12,
        mime_type="image/png",
        s3_key="documents/org-test/abc.png",
    )
    repo.create_document = AsyncMock(return_value=mock_doc)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.document_service.s3_service.upload_file",
        lambda *a, **kw: "documents/org-test/abc.png",
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example/documents/org-test/abc.png",
    )

    file = _upload_file(
        b"fake image bytes", filename="report.png", content_type="image/png", size=12
    )
    user = _make_user(id="usr-123", organization_id="org-test")

    result = await service.upload_document(db, file, current_user=user)

    assert repo.create_document.await_args is not None
    data = repo.create_document.await_args_list[-1].kwargs["data"]
    assert data["organization_id"] == "org-test"
    assert data["uploaded_by"] == "usr-123"
    assert data["filename"] == "report.png"
    assert data["mime_type"] == "image/png"
    assert data["s3_key"] == "documents/org-test/abc.png"
    assert data["file_url"] is None
    assert db.commit.await_count == 1
    assert result["filename"] == "report.png"
    assert result["download_url"].startswith("https://s3.example/")


@pytest.mark.asyncio
async def test_upload_document_sanitizes_filename_and_uses_uuid(monkeypatch):
    repo: Any = DocumentRepository()
    mock_doc = _make_document(
        id="doc-new", filename="evil.png", s3_key="documents/org-test/zzz.png"
    )
    repo.create_document = AsyncMock(return_value=mock_doc)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    captured: dict[str, Any] = {}

    def fake_upload(file_obj, object_name=None, content_type=None):
        captured["object_name"] = object_name
        return object_name

    monkeypatch.setattr("app.services.document_service.s3_service.upload_file", fake_upload)
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda *a, **kw: "https://s3.example/x",
    )

    file = _upload_file(b"x", filename="../../../../etc/passwd.png", content_type="image/png")
    await service.upload_document(db, file, current_user=_make_user())

    object_name = captured["object_name"]
    assert object_name.startswith("documents/org-test/")
    assert "passwd" not in object_name  # no traversal
    assert object_name.endswith(".png")
    # uuid-like segment
    seg = object_name.rsplit("/", 1)[-1]
    stem = seg.rsplit(".", 1)[0]
    assert len(stem) == 32  # uuid4 hex
    # Filename persisted is sanitized
    assert repo.create_document.await_args is not None
    persisted = repo.create_document.await_args_list[-1].kwargs["data"]["filename"]
    assert ".." not in persisted
    assert "/" not in persisted


@pytest.mark.asyncio
async def test_upload_document_rejects_traversal_filename(monkeypatch):
    repo: Any = DocumentRepository()
    repo.create_document = AsyncMock(return_value=_make_document())
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.document_service.s3_service.upload_file", lambda *a, **kw: "x"
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url", lambda *a, **kw: "x"
    )

    file = _upload_file(b"x", filename="../../something.png", content_type="image/png")
    await service.upload_document(db, file, current_user=_make_user())
    assert repo.create_document.await_args is not None
    persisted = repo.create_document.await_args_list[-1].kwargs["data"]["filename"]
    assert ".." not in persisted and "/" not in persisted


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_mime():
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    file = _upload_file(b"x", filename="evil.exe", content_type="application/x-msdownload")
    with pytest.raises(APIException) as exc:
        await service.upload_document(db, file, current_user=_make_user())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_extension():
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    file = _upload_file(b"x", filename="something.png.exe", content_type="image/png")
    with pytest.raises(APIException) as exc:
        await service.upload_document(db, file, current_user=_make_user())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_document_rejects_oversize(monkeypatch):
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.document_service.settings.MAX_DOCUMENT_UPLOAD_SIZE", 10)
    file = _upload_file(b"x" * 50, filename="big.png", content_type="image/png", size=50)
    with pytest.raises(APIException) as exc:
        await service.upload_document(db, file, current_user=_make_user())
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_document_rejects_oversize_during_stream(monkeypatch):
    repo: Any = DocumentRepository()
    repo.create_document = AsyncMock(return_value=_make_document())
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.document_service.settings.MAX_DOCUMENT_UPLOAD_SIZE", 5)
    monkeypatch.setattr("app.services.document_service.settings.DOCUMENT_UPLOAD_BUFFER_BYTES", 2)

    async def fake_read(size):
        return b"x" * size  # always returns a full chunk, never empty

    f = UploadFile(
        filename="big.png", file=io.BytesIO(b""), headers=Headers({"content-type": "image/png"})
    )
    f.read = fake_read  # type: ignore[assignment]

    with pytest.raises(APIException) as exc:
        await service.upload_document(db, f, current_user=_make_user())
    assert exc.value.status_code == 413
    repo.create_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_document_raises_forbidden_without_user():
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    file = _upload_file(b"x", filename="a.png", content_type="image/png")
    with pytest.raises(ForbiddenError):
        await service.upload_document(db, file, current_user=None)


@pytest.mark.asyncio
async def test_upload_document_raises_502_on_s3_error(monkeypatch):
    repo: Any = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.document_service.s3_service.upload_file",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("s3 timeout")),
    )

    file = _upload_file(b"x", filename="a.png", content_type="image/png")
    with pytest.raises(APIException) as exc:
        await service.upload_document(db, file, current_user=_make_user())
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_cross_org_document_is_invisible(monkeypatch):
    repo: Any = DocumentRepository()
    repo.get_document = AsyncMock(return_value=None)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(organization_id="org-A")
    with pytest.raises(NotFoundError):
        await service.get_document(db, "doc-from-org-B", current_user=user)
