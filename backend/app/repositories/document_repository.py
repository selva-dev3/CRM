from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, User


class DocumentRepository:
    """Query layer for the Document domain — no business logic."""

    async def list_documents(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
    ) -> Sequence[Document]:
        stmt = select(Document)
        if search and search.strip():
            stmt = stmt.where(Document.filename.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Document.uploaded_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> Sequence[Document]:
        stmt = select(Document).where(Document.id.in_(ids))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_document(self, db: AsyncSession, document_id: str) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_document(self, db: AsyncSession, *, data: dict) -> Document:
        document = Document(**data)
        db.add(document)
        return document

    async def delete_document(self, db: AsyncSession, document: Document) -> None:
        await db.delete(document)

    async def resolve_user_id(self, db: AsyncSession) -> Optional[str]:
        res = await db.execute(select(User).limit(1))
        user = res.scalars().first()
        return user.id if user else None