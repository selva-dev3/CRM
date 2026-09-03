from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError

from app.services.s3_service import S3Service


def _service() -> S3Service:
    service = S3Service.__new__(S3Service)
    service.bucket_name = "crm-enterprise-bucket"
    service._bucket_verified = False
    service.s3_client = Mock()
    return service


def _client_error(code: str, status_code: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        "HeadBucket",
    )


def test_ensure_bucket_exists_marks_existing_bucket_verified():
    service = _service()

    service._ensure_bucket_exists()

    service.s3_client.head_bucket.assert_called_once_with(Bucket=service.bucket_name)
    service.s3_client.create_bucket.assert_not_called()
    assert service._bucket_verified is True


def test_ensure_bucket_exists_creates_explicitly_missing_bucket():
    service = _service()
    service.s3_client.head_bucket.side_effect = _client_error("NoSuchBucket", 404)

    service._ensure_bucket_exists()

    service.s3_client.create_bucket.assert_called_once_with(Bucket=service.bucket_name)
    assert service._bucket_verified is True


@pytest.mark.parametrize(
    ("error_code", "status_code"),
    [("429", 429), ("InternalError", 502), ("AccessDenied", 403)],
)
def test_ensure_bucket_exists_reraises_non_missing_s3_errors(error_code: str, status_code: int):
    service = _service()
    error = _client_error(error_code, status_code)
    service.s3_client.head_bucket.side_effect = error

    with pytest.raises(ClientError) as exc_info:
        service._ensure_bucket_exists()

    assert exc_info.value is error
    service.s3_client.create_bucket.assert_not_called()
    assert service._bucket_verified is False


@pytest.mark.parametrize(
    "error",
    [
        EndpointConnectionError(endpoint_url="https://minio.example"),
        ConnectTimeoutError(endpoint_url="https://minio.example", error=TimeoutError("timed out")),
    ],
)
def test_ensure_bucket_exists_reraises_connection_and_timeout_errors(error: Exception):
    service = _service()
    service.s3_client.head_bucket.side_effect = error

    with pytest.raises(type(error)) as exc_info:
        service._ensure_bucket_exists()

    assert exc_info.value is error
    service.s3_client.create_bucket.assert_not_called()
    assert service._bucket_verified is False
