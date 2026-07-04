"""
Public AWS service for generating pre-signed URLs using the
public-facing endpoint.

Used exclusively for client-facing asset delivery, so URLs are resolvable
outside the server network.
"""

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from src.api.core.config import settings
from src.api.core.logger import logger


class PublicAwsService:
    """
    Generates pre-signed URLs for the assets bucket using the public
    MinIO endpoint (MINIO_PUBLIC_ENDPOINT_URL).
    """

    def __init__(self):
        self.assets_bucket: str = settings.AWS_S3_ASSETS_BUCKET_NAME

        self.s3: S3Client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.MINIO_PUBLIC_ENDPOINT_URL or None,
            region_name=settings.AWS_REGION,
        )

    def generate_presigned_url(self, key: str, expiration_time: int = 1800) -> str:
        """
        Generate a pre-signed URL for an asset in the assets bucket.
        :param key: The S3 object key e.g. '{map_id}/assets/icon.png'.
        :param expiration_time: URL expiry in seconds, default 30 minutes.
        :return: Pre-signed URL resolvable by the client.
        """
        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.assets_bucket, "Key": key},
                ExpiresIn=expiration_time,
            )
        except ClientError as exc:
            logger.error("Failed to generate pre-signed url for '%s': %s", key, exc)
            raise

    def generate_presigned_url_from_uri(self, uri: str, expiration_time: int = 1800) -> str:
        """
        Generate a pre-signed URL directly from an S3 URI.
        :param uri: Full S3 URI e.g. 's3://farmhand-assets/{map_id}/assets/icon.png'.
        :param expiration_time: URL expiry in seconds, default 30 minutes.
        :return: Pre-signed URL resolvable by the client.
        """
        key = uri.split("/", 3)[-1].strip().strip('"')
        return self.generate_presigned_url(key, expiration_time)
