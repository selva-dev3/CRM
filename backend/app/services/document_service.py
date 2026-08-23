import asyncio
import io
from typing import Optional

from fastapi import status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models import Document, User
from app.repositories.document_repository import DocumentRepository
from app.services.s3_service import s3_service

logger = get_logger(__name__)


def document_to_dict(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "file_size": document.file_size or 0,
        "mime_type": document.mime_type or "application/octet-stream",
        "download_url": document.file_url or "",
        "uploaded_at": str(document.uploaded_at),
    }


class DocumentService:
    """Business logic for the Document domain with strict multi-tenant isolation."""

    def __init__(self, repository: Optional[DocumentRepository] = None) -> None:
        self.repository = repository or DocumentRepository()

    def _resolve_auth(self, current_user: Optional[User]) -> tuple[str, str]:
        """Strictly validate authenticated user and organization context."""
        org_id = current_user.organization_id if current_user and getattr(current_user, "organization_id", None) else None
        user_id = current_user.id if current_user and getattr(current_user, "id", None) else None

        if not org_id or not user_id:
            raise ForbiddenError(
                message="Organization context is required. Please ensure your account is associated with an organization."
            )
        return org_id, user_id

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.exception("Database commit error: %s", error_message)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=error_message
            ) from e

    async def list_documents(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> list[dict]:
        org_id, _ = self._resolve_auth(current_user)
        documents = await self.repository.list_documents(
            db, org_id=org_id, page=page, limit=limit, search=search
        )
        return [document_to_dict(d) for d in documents]

    async def upload_document(
        self, db: AsyncSession, file: UploadFile, current_user: Optional[User] = None
    ) -> dict:
        org_id, user_id = self._resolve_auth(current_user)
        file_bytes = await file.read()
        file_size = len(file_bytes)

        object_name = f"documents/{org_id}/{file.filename}"
        try:
            file_stream = io.BytesIO(file_bytes)
            s3_key = await asyncio.to_thread(
                s3_service.upload_file,
                file_stream,
                object_name=object_name,
                content_type=file.content_type,
            )
            presigned_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
        except Exception as e:
            logger.exception("S3 upload failed for document %s (org=%s)", file.filename, org_id)
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to upload document to storage. Please try again later.",
            ) from e

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
        await self._commit(db, "Failed to record uploaded document")
        await db.refresh(document)
        return {
            "id": document.id,
            "filename": document.filename,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "download_url": document.file_url,
            "uploaded_at": str(document.uploaded_at),
        }

    async def get_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        return document_to_dict(document)

    async def download_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        try:
            object_key = f"documents/{org_id}/{document.filename}"
            url = await asyncio.to_thread(s3_service.generate_presigned_url, object_key)
        except Exception as e:
            logger.exception("Failed to generate presigned download URL for document %s", document_id)
            if document.file_url:
                url = document.file_url
            else:
                raise APIException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    message="Failed to generate document download link. Please try again later.",
                ) from e
        return {"download_url": url, "filename": document.filename, "expires_in": 3600}

    async def delete_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        try:
            try:
                await asyncio.to_thread(s3_service.delete_file, f"documents/{org_id}/{document.filename}")
            except Exception:
                logger.warning("Failed to delete S3 file for document %s", document_id, exc_info=True)
            await self.repository.delete_document(db, document)
            await self._commit(db, "Failed to delete document")
            return {"message": f"Document {document_id} deleted", "status": "success"}
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Failed to delete document %s", document_id)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to delete document. Please try again later.",
            ) from e

    async def bulk_delete(
        self, db: AsyncSession, ids: list[str], current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        documents = await self.repository.list_by_ids(db, ids, org_id)
        for document in documents:
            try:
                await asyncio.to_thread(s3_service.delete_file, f"documents/{org_id}/{document.filename}")
            except Exception:
                logger.warning("Failed to delete S3 file for document %s during bulk delete", document.id, exc_info=True)
            await self.repository.delete_document(db, document)
        await self._commit(db, "Failed to bulk delete documents")
        return {"affected_count": len(documents), "message": f"Successfully deleted {len(documents)} documents"}


document_service = DocumentService()