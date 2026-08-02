import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import BinaryIO, Optional
from app.config import settings


class S3Service:
    def __init__(self):
        self.endpoint_url = settings.AWS_ENDPOINT_URL
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.region = settings.AWS_REGION
        self.bucket_name = settings.AWS_S3_BUCKET

        # Configure boto3 client for MinIO (path-style addressing + S3v4 signature) using central Settings
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"}
            )
        )

    def upload_file(self, file_obj: BinaryIO, object_name: str, content_type: Optional[str] = None) -> str:
        """Uploads a file object to MinIO S3 bucket and returns the object key."""
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.s3_client.upload_fileobj(
                Fileobj=file_obj,
                Bucket=self.bucket_name,
                Key=object_name,
                ExtraArgs=extra_args
            )
            return object_name
        except ClientError as e:
            raise RuntimeError(f"Failed to upload object {object_name} to S3: {str(e)}")

    def generate_presigned_url(self, object_name: str, expiration_seconds: int = 3600) -> str:
        """Generates a temporary presigned GET URL for secure client downloads."""
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration_seconds
            )
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate presigned URL for {object_name}: {str(e)}")

    def delete_file(self, object_name: str) -> bool:
        """Deletes an object from MinIO S3 bucket."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            raise RuntimeError(f"Failed to delete object {object_name}: {str(e)}")


s3_service = S3Service()
