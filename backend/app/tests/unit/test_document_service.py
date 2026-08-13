from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Document
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService, document_to_dict


def _make_document(**overrides) -> Document:
    defaults = {
        "id": "doc-1",
        "organization_id": "org-1",
        "folder_id": None,
        "filename": "proposal.pdf",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "file_url": "https://storage.example/doc-1",
        "uploaded_by": "user-1",
        "uploaded_at": datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Document(**defaults)


@pytest.mark.asyncio
async def test_list_documents_maps_rows():
    repo = DocumentRepository()
    repo.list_documents = AsyncMock(return_value=[_make_document()])
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_documents(db, page=1, limit=20, search="proposal")

    assert result[0]["filename"] == "proposal.pdf"
    assert result[0]["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_get_document_not_found():
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=None)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_document(db, "missing")


@pytest.mark.asyncio
async def test_download_document_falls_back_to_file_url(monkeypatch):
    document = _make_document()
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    def boom(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url", boom
    )

    result = await service.download_document(db, "doc-1")

    assert result["download_url"] == document.file_url
    assert result["expires_in"] == 3600


@pytest.mark.asyncio
async def test_delete_document_commit():
    document = _make_document()
    repo = DocumentRepository()
    repo.get_document = AsyncMock(return_value=document)
    repo.delete_document = AsyncMock()
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.delete_document(db, "doc-1")

    repo.delete_document.assert_awaited_once_with(db, document)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_bulk_delete_returns_affected_count():
    repo = DocumentRepository()
    repo.list_by_ids = AsyncMock(return_value=[_make_document(), _make_document(id="doc-2")])
    service = DocumentService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete(db, ["doc-1", "doc-2"])

    assert result["affected_count"] == 2
    db.commit.assert_awaited_once()


def test_document_to_dict_uses_fallbacks():
    doc = _make_document(file_size=None, mime_type=None, file_url=None)
    result = document_to_dict(doc)
    assert result["file_size"] == 0
    assert result["mime_type"] == "application/octet-stream"
    assert result["download_url"] == "https://api.crm.com/documents/doc-1/download"