from datetime import timedelta
from io import SEEK_END, SEEK_SET
from typing import BinaryIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class _MinioClientCompatibilityAdapter:
    """Expose the legacy get_object shape used by an existing service caller."""

    def __init__(self, client: Minio) -> None:
        self._client = client

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": self._client.get_object(Bucket, Key)}


class S3Service:
    def __init__(self):
        self.endpoint_url = settings.AWS_ENDPOINT_URL
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.region = settings.AWS_REGION
        self.bucket_name = settings.AWS_S3_BUCKET
        self._bucket_verified = False

        parsed_endpoint = urlparse(self.endpoint_url)
        if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
            raise ValueError("AWS_ENDPOINT_URL must be a valid HTTP or HTTPS URL")

        self.minio_client = Minio(
            parsed_endpoint.netloc,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=parsed_endpoint.scheme == "https",
            region=self.region,
        )
        self.s3_client = _MinioClientCompatibilityAdapter(self.minio_client)

    def _ensure_bucket_exists(self) -> None:
        """Ensures the S3 bucket exists before performing operations."""
        if self._bucket_verified:
            return

        try:
            bucket_exists = self.minio_client.bucket_exists(self.bucket_name)
        except Exception:
            logger.exception(
                "S3 bucket check failed for bucket=%s; not attempting bucket creation",
                self.bucket_name,
            )
            raise

        if bucket_exists:
            self._bucket_verified = True
            return

        logger.info("S3 bucket=%s does not exist; attempting to create it", self.bucket_name)
        try:
            self.minio_client.make_bucket(self.bucket_name, location=self.region)
            self._bucket_verified = True
        except Exception:
            logger.exception("Failed to create missing S3 bucket=%s", self.bucket_name)
            raise

    @staticmethod
    def _stream_length(file_obj: BinaryIO) -> int:
        """Return the remaining stream length while preserving its position."""
        try:
            position = file_obj.tell()
            file_obj.seek(0, SEEK_END)
            length = file_obj.tell() - position
            file_obj.seek(position, SEEK_SET)
            return length
        except (AttributeError, OSError):
            return -1

    def upload_file(
        self, file_obj: BinaryIO, object_name: str, content_type: str | None = None
    ) -> str:
        """Uploads a file object to MinIO S3 bucket and returns the object key."""
        self._ensure_bucket_exists()
        try:
            self.minio_client.put_object(
                self.bucket_name,
                object_name,
                file_obj,
                self._stream_length(file_obj),
                content_type=content_type or "application/octet-stream",
            )
            return object_name
        except S3Error as exc:
            raise RuntimeError(f"Failed to upload object {object_name} to S3: {exc}") from exc

    def generate_presigned_url(self, object_name: str, expiration_seconds: int = 3600) -> str:
        """Generates a temporary presigned GET URL for secure client downloads."""
        try:
            return self.minio_client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expiration_seconds),
            )
        except S3Error as exc:
            raise RuntimeError(
                f"Failed to generate presigned URL for {object_name}: {exc}"
            ) from exc

    def delete_file(self, object_name: str) -> bool:
        """Deletes an object from MinIO S3 bucket."""
        try:
            self.minio_client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as exc:
            raise RuntimeError(f"Failed to delete object {object_name}: {exc}") from exc


s3_service = S3Service()
