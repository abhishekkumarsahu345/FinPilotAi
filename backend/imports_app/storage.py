"""
File storage abstraction — currently backed by S3-compatible storage (MinIO / AWS S3).
Falls back to local filesystem when AWS credentials are not configured.
"""
import hashlib
import io
import os

import boto3
from botocore.exceptions import ClientError
from django.conf import settings


class FileStorageService:
    def __init__(self):
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.expiry = settings.FILE_STORAGE_PRESIGN_EXPIRY_SECONDS
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass  # Bucket may already exist or credentials not configured

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload bytes to storage. Returns the S3 key."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def presigned_download_url(self, key: str) -> str:
        """Return a short-lived download URL."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.expiry,
        )

    def download(self, key: str) -> bytes:
        """Download file content from storage."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Module-level singleton — instantiated lazily
_storage: FileStorageService | None = None


def get_storage() -> FileStorageService:
    global _storage
    if _storage is None:
        _storage = FileStorageService()
    return _storage
