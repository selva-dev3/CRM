import asyncio
import io
import os
import re
import uuid
from typing import Any, Optional

from fastapi import status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models import Document, User
from app.repositories.document_repository import DocumentRepository
from app.services.s3_service import s3_service

logger = get_logger(__name__)


_ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
    "image/gif": {".gif"},
    "text/plain": {".txt"},
    "text/csv": {".csv"},
    "application/vnd.ms-excel": {".xls"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/zip": {".zip"},
    "application/json": {".json"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
}

_ALLOWED_EXTENSIONS: set[str] = {ext for exts in _ALLOWED_MIME_TYPES.values() for ext in exts}

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_filename(raw: Optional[str]) -> str:
    """Reduce a client-supplied filename to a safe basename.

    - strips any path components
    - removes control characters
    - replaces non-alphanumeric characters with underscores
    - caps length and provides a fallback if empty
    """
    if not raw:
        return "document"
    name = os.path.basename(raw).strip()
    name = _CONTROL_CHARS_RE.sub("", name)
    name = _FILENAME_SAFE_RE.sub("_", name)
    name = name.strip("._-")
    if not name:
        return "document"
    return name[:200]


def _split_extension(filename: str) -> tuple[str, str]:
    """Split sanitized filename into (stem, lowercased extension with leading dot)."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if not ext or len(ext) > 10:
        return filename, ""
    return filename, ext


def _normalize_mime_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    primary = content_type.split(";", 1)[0].strip().lower()
    return primary or None


def _validate_upload(filename: str, content_type: Optional[str], declared_size: Optional[int]) -> None:
    """Reject unsupported files BEFORE any S3 I/O.

    Returns silently on success; raises APIException with a 400/422 on failure.
    """
    stem, ext = _split_extension(filename)
    if not ext:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="File must include a supported extension.",
        )
    if ext not in _ALLOWED_EXTENSIONS:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Unsupported file extension '{ext}'.",
        )

    mime = _normalize_mime_type(content_type)
    if mime not in _ALLOWED_MIME_TYPES:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Unsupported content type '{content_type}'.",
        )

    if ext not in _ALLOWED_MIME_TYPES[mime]:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="File extension does not match the declared content type.",
        )

    max_size = int(getattr(settings, "MAX_DOCUMENT_UPLOAD_SIZE", 0) or 0)
    if max_size and declared_size is not None and declared_size > max_size:
        raise APIException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            message=f"File exceeds the maximum allowed size of {max_size} bytes.",
        )


def _build_object_key(org_id: str, ext: str) -> str:
    """Build a tenant-scoped, unique S3 object key."""
    safe_org = re.sub(r"[^A-Za-z0-9_-]", "_", str(org_id or "unknown"))[:64]
    return f"documents/{safe_org}/{uuid.uuid4().hex}{ext}"


async def _read_upload_with_limit(file: UploadFile, max_size: int) -> bytes:
    """Stream-read the upload enforcing an upper bound without buffering unbounded files.

    Raises APIException 413 if the file exceeds the limit.
    """
    chunk_size = int(getattr(settings, "DOCUMENT_UPLOAD_BUFFER_BYTES", 1024 * 1024) or 1024 * 1024)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if max_size and total > max_size:
            raise APIException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                message=f"File exceeds the maximum allowed size of {max_size} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _generate_fresh_url(s3_key: str) -> str:
    """Generate a fresh presigned URL or raise a sanitized 502 error."""
    try:
        return await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
    except Exception as exc:
        logger.exception("Failed to generate presigned URL for s3_key=%s", s3_key)
        raise APIException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            message="Failed to generate download link. Please try again later.",
        ) from exc


async def _safe_delete_s3(s3_key: Optional[str], document_id: str) -> None:
    """Best-effort S3 deletion logged but never raised."""
    if not s3_key:
        return
    try:
        await asyncio.to_thread(s3_service.delete_file, s3_key)
    except Exception:
        logger.warning(
            "Failed to delete S3 object %s for document %s",
            s3_key,
            document_id,
            exc_info=True,
        )


def document_to_dict(document: Document, download_url: str = "") -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "file_size": document.file_size or 0,
        "mime_type": document.mime_type or "application/octet-stream",
        "download_url": download_url,
        "uploaded_at": str(document.uploaded_at),
    }


class DocumentService:
    """Business logic for the Document domain with strict multi-tenant isolation."""

    def __init__(self, repository: Optional[DocumentRepository] = None) -> None:
        self.repository = repository or DocumentRepository()

    def _resolve_auth(self, current_user: Optional[User]) -> tuple[str, str]:
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
        out: list[dict] = []
        for doc in documents:
            s3_key = getattr(doc, "s3_key", None)
            download_url = await _generate_fresh_url(s3_key) if s3_key else ""
            out.append(document_to_dict(doc, download_url=download_url))
        return out

    async def upload_document(
        self, db: AsyncSession, file: UploadFile, current_user: Optional[User] = None
    ) -> dict:
        org_id, user_id = self._resolve_auth(current_user)

        safe_filename = _sanitize_filename(file.filename)
        _, ext = _split_extension(safe_filename)
        max_size = int(getattr(settings, "MAX_DOCUMENT_UPLOAD_SIZE", 0) or 0)

        try:
            declared_size: Optional[int] = getattr(file, "size", None)
        except Exception:
            declared_size = None

        _validate_upload(safe_filename, file.content_type, declared_size)

        try:
            file_bytes = await _read_upload_with_limit(file, max_size)
        except APIException:
            raise
        except Exception as exc:
            logger.exception("Failed to read upload stream")
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to read uploaded file.",
            ) from exc

        file_size = len(file_bytes)
        if max_size and file_size > max_size:
            raise APIException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                message=f"File exceeds the maximum allowed size of {max_size} bytes.",
            )

        object_key = _build_object_key(org_id, ext)
        try:
            file_stream = io.BytesIO(file_bytes)
            stored_key = await asyncio.to_thread(
                s3_service.upload_file,
                file_stream,
                object_name=object_key,
                content_type=_normalize_mime_type(file.content_type),
            )
            download_url = await asyncio.to_thread(s3_service.generate_presigned_url, stored_key)
        except Exception as e:
            logger.exception(
                "S3 upload failed for document %s (org=%s)",
                safe_filename,
                org_id,
            )
            raise APIException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                message="Failed to upload document to storage. Please try again later.",
            ) from e

        document = await self.repository.create_document(
            db,
            data={
                "organization_id": org_id,
                "filename": safe_filename,
                "file_url": None,
                "s3_key": stored_key,
                "file_size": file_size,
                "mime_type": _normalize_mime_type(file.content_type) or "application/octet-stream",
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
            "download_url": download_url,
            "uploaded_at": str(document.uploaded_at),
        }

    async def get_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")
        s3_key = getattr(document, "s3_key", None)
        download_url = await _generate_fresh_url(s3_key) if s3_key else ""
        return document_to_dict(document, download_url=download_url)

    async def download_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")

        s3_key = getattr(document, "s3_key", None)
        if not s3_key:
            logger.warning(
                "Document %s has no stored s3_key; refusing to return expired legacy URL",
                document_id,
            )
            raise APIException(
                status_code=status.HTTP_410_GONE,
                message="This document is no longer available. Please ask the uploader to re-upload.",
            )

        url = await _generate_fresh_url(s3_key)
        return {"download_url": url, "filename": document.filename, "expires_in": 3600}

    async def delete_document(
        self, db: AsyncSession, document_id: str, current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        document = await self.repository.get_document(db, document_id, org_id)
        if not document:
            raise NotFoundError(message=f"Document '{document_id}' not found")

        s3_key = getattr(document, "s3_key", None)
        try:
            await self.repository.delete_document(db, document)
            await self._commit(db, "Failed to delete document")
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Failed to delete document %s", document_id)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to delete document. Please try again later.",
            ) from e

        # Best-effort storage cleanup after the DB commit has succeeded.
        await _safe_delete_s3(s3_key, document_id)
        return {"message": f"Document {document_id} deleted", "status": "success"}

    async def bulk_delete(
        self, db: AsyncSession, ids: list[str], current_user: Optional[User] = None
    ) -> dict:
        org_id, _ = self._resolve_auth(current_user)
        documents = await self.repository.list_by_ids(db, ids, org_id)
        s3_keys_to_cleanup: list[tuple[str, str]] = []
        try:
            for document in documents:
                s3_keys_to_cleanup.append((getattr(document, "s3_key", None) or "", document.id))
                await self.repository.delete_document(db, document)
            await self._commit(db, "Failed to bulk delete documents")
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Failed to bulk delete documents for org=%s", org_id)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Unable to bulk delete documents. Please try again later.",
            ) from e

        # Best-effort storage cleanup after the DB commit has succeeded.
        for s3_key, doc_id in s3_keys_to_cleanup:
            await _safe_delete_s3(s3_key, doc_id)

        return {
            "affected_count": len(documents),
            "message": f"Successfully deleted {len(documents)} documents",
        }


document_service = DocumentService()
