from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document
from app.repositories.document_repository import DocumentRepository


def _db_returning(value, method="scalars_first") -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    if method == "scalar_one_or_none":
        result.scalar_one_or_none.return_value = value
    elif method == "scalars_all":
        scalars = MagicMock()
        scalars.all.return_value = value
        result.scalars.return_value = scalars
    elif method == "scalars_first":
        scalars = MagicMock()
        scalars.first.return_value = value
        result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_document_filters_by_org_and_returns_row():
    repo = DocumentRepository()
    doc = Document(id="doc-1", organization_id="org-1", filename="a.pdf", s3_key="documents/org-1/x.pdf")
    db = _db_returning(doc)

    found = await repo.get_document(db, "doc-1", "org-1")

    assert found is doc
    stmt = db.execute.await_args.args[0]
    sql = str(stmt)
    assert "organization_id" in sql


@pytest.mark.asyncio
async def test_get_document_returns_none_for_cross_org():
    repo = DocumentRepository()
    db = _db_returning(None)

    found = await repo.get_document(db, "doc-foreign", "org-other")
    assert found is None


@pytest.mark.asyncio
async def test_list_by_ids_scopes_to_org():
    repo = DocumentRepository()
    doc = Document(id="doc-1", organization_id="org-1", filename="a.pdf", s3_key="k")
    db = _db_returning([doc], method="scalars_all")

    rows = await repo.list_by_ids(db, ["doc-1"], "org-1")

    assert rows == [doc]
    stmt = db.execute.await_args.args[0]
    assert "organization_id" in str(stmt)


@pytest.mark.asyncio
async def test_create_document_persists_s3_key():
    repo = DocumentRepository()
    db = AsyncMock(spec=AsyncSession)

    doc = await repo.create_document(
        db,
        data={
            "organization_id": "org-1",
            "filename": "a.pdf",
            "file_url": None,
            "s3_key": "documents/org-1/abc.pdf",
            "file_size": 10,
            "mime_type": "application/pdf",
            "uploaded_by": "usr-1",
        },
    )

    db.add.assert_called_once_with(doc)
    assert doc.s3_key == "documents/org-1/abc.pdf"
    assert doc.file_url is None
