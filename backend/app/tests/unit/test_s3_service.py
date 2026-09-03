from io import BytesIO
from unittest.mock import Mock

import pytest
from minio.error import S3Error, ServerError

from app.services.s3_service import S3Service


def _service() -> S3Service:
    service = S3Service.__new__(S3Service)
    service.bucket_name = "crm-enterprise-bucket"
    service.region = "us-east-1"
    service._bucket_verified = False
    service.minio_client = Mock()
    return service


def _s3_error(code: str, status_code: str) -> S3Error:
    response = Mock()
    response.status = int(status_code)
    return S3Error(response, code, code, "crm-enterprise-bucket", "request-id", "host-id")


def test_ensure_bucket_exists_marks_existing_bucket_verified():
    service = _service()
    service.minio_client.bucket_exists.return_value = True

    service._ensure_bucket_exists()

    service.minio_client.bucket_exists.assert_called_once_with(service.bucket_name)
    service.minio_client.make_bucket.assert_not_called()
    assert service._bucket_verified is True


def test_ensure_bucket_exists_creates_missing_bucket():
    service = _service()
    service.minio_client.bucket_exists.return_value = False

    service._ensure_bucket_exists()

    service.minio_client.make_bucket.assert_called_once_with(
        service.bucket_name, location=service.region
    )
    assert service._bucket_verified is True


@pytest.mark.parametrize(
    "error",
    [
        _s3_error("TooManyRequests", "429"),
        _s3_error("InternalError", "502"),
        _s3_error("AccessDenied", "403"),
        TimeoutError("timed out"),
        ConnectionError("connection failed"),
    ],
)
def test_ensure_bucket_exists_does_not_create_after_storage_errors(error: Exception):
    service = _service()
    service.minio_client.bucket_exists.side_effect = error

    with pytest.raises(type(error)) as exc_info:
        service._ensure_bucket_exists()

    assert exc_info.value is error
    service.minio_client.make_bucket.assert_not_called()
    assert service._bucket_verified is False


def test_upload_file_uses_minio_put_object():
    service = _service()
    service._ensure_bucket_exists = Mock()
    stream = BytesIO(b"document")

    result = service.upload_file(stream, "documents/test.txt", "text/plain")

    assert result == "documents/test.txt"
    service.minio_client.put_object.assert_called_once_with(
        service.bucket_name,
        "documents/test.txt",
        stream,
        8,
        content_type="text/plain",
    )
    service._ensure_bucket_exists.assert_not_called()
    service.minio_client.bucket_exists.assert_not_called()


def test_upload_file_preserves_default_content_type():
    service = _service()
    stream = BytesIO(b"document")

    result = service.upload_file(stream, "documents/test.bin")

    assert result == "documents/test.bin"
    assert service.minio_client.put_object.call_args.kwargs["content_type"] == (
        "application/octet-stream"
    )


@pytest.mark.parametrize(
    "error",
    [
        _s3_error("AccessDenied", "403"),
        ServerError("server failed with HTTP status code 429", 429),
    ],
)
def test_upload_file_wraps_minio_errors(error: Exception):
    service = _service()
    service.minio_client.put_object.side_effect = error

    with pytest.raises(RuntimeError, match="Failed to upload object documents/test.txt"):
        service.upload_file(BytesIO(b"document"), "documents/test.txt", "text/plain")


def test_generate_presigned_url_uses_minio_presigned_get_object():
    service = _service()
    service.minio_client.presigned_get_object.return_value = "https://s3.example/signed"

    result = service.generate_presigned_url("documents/test.txt", expiration_seconds=120)

    assert result == "https://s3.example/signed"
    call = service.minio_client.presigned_get_object.call_args
    assert call.args[:2] == (service.bucket_name, "documents/test.txt")
    assert call.kwargs["expires"].total_seconds() == 120


def test_delete_file_uses_minio_remove_object():
    service = _service()

    result = service.delete_file("documents/test.txt")

    assert result is True
    service.minio_client.remove_object.assert_called_once_with(
        service.bucket_name, "documents/test.txt"
    )
