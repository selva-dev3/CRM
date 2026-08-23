from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
        "file_url": "https://storage.example/doc-1",
        "uploaded_by": "usr-123",
        "uploaded_at": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Document(**defaults)


@pytest.mark.asyncio
async def test_list_documents_maps_rows_and_isolates_org():
    repo = DocumentRepository()
    repo.list_documents = AsyncMock(return_value=[_make_document()])
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(organization_id="org-test")

    result = await service.list_documents(db, page=1, limit=20, search="proposal", current_user=user)

    repo.list_documents.assert_awaited_once_with(
        db, org_id="org-test", page=1, limit=20, search="proposal"
    )
    assert result[0]["filename"] == "proposal.pdf"
    assert result[0]["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_list_documents_requires_user_with_org():
    repo = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError):
        await service.list_documents(db, page=1, limit=20, current_user=None)


@pytest.mark.asyncio
async def test_get_document_not_found():
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=None)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    with pytest.raises(NotFoundError):
        await service.get_document(db, "missing", current_user=user)


@pytest.mark.asyncio
async def test_download_document_uses_presigned_or_fallback(monkeypatch):
    document = _make_document()
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url", boom
    )

    result = await service.download_document(db, "doc-1", current_user=user)

    assert result["download_url"] == document.file_url
    assert result["expires_in"] == 3600


@pytest.mark.asyncio
async def test_download_document_raises_502_when_no_fallback(monkeypatch):
    document = _make_document(file_url="")
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url", boom
    )

    with pytest.raises(APIException) as exc_info:
        await service.download_document(db, "doc-1", current_user=user)
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_delete_document_commit():
    document = _make_document()
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    result = await service.delete_document(db, "doc-1", current_user=user)

    repo.delete_document.assert_awaited_once_with(db, document)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_bulk_delete_returns_affected_count():
    repo = DocumentRepository()
    repo.list_by_ids = AsyncMock(return_value=[_make_document(), _make_document(id="doc-2")])
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    result = await service.bulk_delete(db, ["doc-1", "doc-2"], current_user=user)

    assert result["affected_count"] == 2
    db.commit.assert_awaited_once()


def test_document_to_dict_uses_fallbacks():
    doc = _make_document(file_size=None, mime_type=None, file_url=None)
    result = document_to_dict(doc)
    assert result["file_size"] == 0
    assert result["mime_type"] == "application/octet-stream"
    assert result["download_url"] == ""


@pytest.mark.asyncio
async def test_upload_document_creates_record_with_user(monkeypatch):
    repo = DocumentRepository()
    mock_doc = _make_document(id="doc-new", filename="1.png", file_size=4320000, mime_type="image/png")
    repo.create_document = AsyncMock(return_value=mock_doc)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.document_service.s3_service.upload_file", lambda *a, **kw: "documents/org-test/1.png")
    monkeypatch.setattr("app.services.document_service.s3_service.generate_presigned_url", lambda *a, **kw: "https://s3.example/documents/org-test/1.png")

    mock_upload_file = AsyncMock()
    mock_upload_file.filename = "1.png"
    mock_upload_file.content_type = "image/png"
    mock_upload_file.read = AsyncMock(return_value=b"fake image bytes")

    user = _make_user(id="usr-123", organization_id="org-test")

    result = await service.upload_document(db, mock_upload_file, current_user=user)

    assert repo.create_document.await_args is not None
    data = repo.create_document.await_args.kwargs["data"]
    assert data["organization_id"] == "org-test"
    assert data["uploaded_by"] == "usr-123"
    assert data["filename"] == "1.png"
    assert data["mime_type"] == "image/png"
    db.commit.assert_awaited_once()
    assert result["filename"] == "1.png"


@pytest.mark.asyncio
async def test_upload_document_raises_forbidden_without_user():
    repo = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    mock_upload_file = AsyncMock()
    mock_upload_file.filename = "1.png"

    with pytest.raises(ForbiddenError):
        await service.upload_document(db, mock_upload_file, current_user=None)


@pytest.mark.asyncio
async def test_upload_document_raises_502_on_s3_error(monkeypatch):
    repo = DocumentRepository()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    mock_upload_file = AsyncMock()
    mock_upload_file.filename = "1.png"
    mock_upload_file.content_type = "image/png"
    mock_upload_file.read = AsyncMock(return_value=b"fake bytes")

    def boom(*args, **kwargs):
        raise RuntimeError("s3 upload connection timeout")

    monkeypatch.setattr("app.services.document_service.s3_service.upload_file", boom)

    user = _make_user()
    with pytest.raises(APIException) as exc_info:
        await service.upload_document(db, mock_upload_file, current_user=user)
    assert exc_info.value.status_code == 502