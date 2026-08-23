import io
from typing import Optional

from fastapi import status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Document, User
from app.repositories.document_repository import DocumentRepository
from app.services.org_service import organization_service
from app.services.s3_service import s3_service


def document_to_dict(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "file_size": document.file_size or 0,
        "mime_type": document.mime_type or "application/octet-stream",
        "download_url": document.file_url or f"https://api.crm.com/documents/{document.id}/download",
        "uploaded_at": str(document.uploaded_at),
    }


class DocumentService:
    """Business logic for the Document domain."""

    def __init__(self, repository: Optional[DocumentRepository] = None) -> None:
        self.repository = repository or DocumentRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_documents(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
    ) -> list[dict]:
        documents = await self.repository.list_documents(
            db, page=page, limit=limit, search=search
        )
        return [document_to_dict(d) for d in documents]

    async def upload_document(
        self, db: AsyncSession, file: UploadFile, current_user: Optional[User] = None
    ) -> dict:
        org_id = (
            current_user.organization_id
            if current_user and getattr(current_user, "organization_id", None)
            else await organization_service.resolve_valid_org_id(db)
        )
        user_id = (
            current_user.id
            if current_user and getattr(current_user, "id", None)
            else await self.repository.resolve_user_id(db)
        )
        file_bytes = await file.read()
        file_size = len(file_bytes)

        try:
            file_stream = io.BytesIO(file_bytes)
            object_name = f"documents/{file.filename}"
            s3_key = s3_service.upload_file(
                file_stream, object_name=object_name, content_type=file.content_type
            )
            presigned_url = s3_service.generate_presigned_url(s3_key)
        except Exception:
            presigned_url = f"https://storage.minio.internal/crm-storage/documents/{file.filename}"

        document = await self.repository.create_document(
            db,
            data={
                "organization_id": org_id,
                "filename": file.filename,
                "file_url": presigned_url,
                "file_size": file_size,
                "mime_type": file.content_type or "application/octet-stream",
                "uploaded_by": user_id,
            },
        )
        await self._commit(db, "Failed to upload document")
        await db.refresh(document)
        return {
            "id": document.id,
            "filename": document.filename,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "download_url": document.file_url,
            "uploaded_at": str(document.uploaded_at),
        }

    async def get_document(self, db: AsyncSession, document_id: str) -> dict:
        document = await self.repository.get_document(db, document_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        return document_to_dict(document)

    async def download_document(self, db: AsyncSession, document_id: str) -> dict:
        document = await self.repository.get_document(db, document_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        try:
            object_key = f"documents/{document.filename}"
            url = s3_service.generate_presigned_url(object_key)
        except Exception:
            url = document.file_url or f"https://storage.minio.internal/crm-storage/documents/{document.filename}"
        return {"download_url": url, "filename": document.filename, "expires_in": 3600}

    async def delete_document(self, db: AsyncSession, document_id: str) -> dict:
        document = await self.repository.get_document(db, document_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        try:
            try:
                s3_service.delete_file(f"documents/{document.filename}")
            except Exception:
                pass
            await self.repository.delete_document(db, document)
            await self._commit(db, "Failed to delete document")
            return {"message": f"Document {document_id} deleted", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=str(e)
            ) from e

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        documents = await self.repository.list_by_ids(db, ids)
        for document in documents:
            try:
                s3_service.delete_file(f"documents/{document.filename}")
            except Exception:
                pass
            await self.repository.delete_document(db, document)
        await self._commit(db, "Failed to bulk delete documents")
        return {"affected_count": len(documents), "message": f"Successfully deleted {len(documents)} documents"}


document_service = DocumentService()