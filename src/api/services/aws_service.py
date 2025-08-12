"""
Python module containing an AWS service to interact with AWS managed services through
boto3, primarily S3 / MinIO buckets.
"""

from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import Literal, Optional, Union

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from src.api.core.config import settings
from src.api.core.logger import logger
from src.api.utils import extension_to_content_type


class AwsService:
    """
    AWS service class used for uploading items to S3, primary Farming Simulator mod
    maps and their extracted contents.
    """
    def __init__(self, bucket_name: Optional[str] = None):
        """
        Constructor for the AwsService
        :param bucket_name: (str) of the bucket to save content to.
        """
        self.bucket: str = bucket_name or settings.AWS_S3_BUCKET_NAME

        self.s3: S3Client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.MINIO_ENDPOINT_URL or None,
            region_name=settings.AWS_REGION
        )

    def generate_pre_signed_url(
            self,
            object_key: str,
            method_type: Literal["get_object", "put_object"],
            expiration_time=3600
    ) -> Optional[str]:
        """
        Generate a pre-signed URL to upload or view a mod in a farmhand bucket
        :param object_key: the object key to store the mod at.
        :param method_type: A literal of either "get_object" or "put_object".
        :param expiration_time: Pre-signed URL expiry time
        :return: (str) presigned URL location.
        """
        try:
            url = self.s3.generate_presigned_url(
                method_type,
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=expiration_time
            )
            logger.debug("Generated pre-signed url for: %s", object_key)
        except ClientError as exc:
            logger.error("Failed to generate pre-signed url for '%s': %s", object_key, str(exc))
            return None

        return url

    def upload_object(self, file_obj: bytes, mod_id: int, file_name: str) -> str:
        """
        Method to upload a file object to a 'farmhand' bucket.
        :param file_obj: The bytes of the file object.
        :param mod_id: The 'id' of the mod from the ModHub.
        :param file_name: The filename of the object.
        :return: A S3 URI of the location.
        """
        object_key = f"{mod_id}/{file_name}"
        try:
            self.s3.upload_fileobj(BytesIO(file_obj), self.bucket, object_key)
            return f"s3://{self.bucket}/{object_key}"
        except ClientError as exc:
            logger.warning(
                "Failed to upload '%s' to %s. Reason: %s",
                object_key,
                self.bucket,
                str(exc)
            )
            raise

    def upload_directory_contents(self, files: list[Path], root_dir: Path, object_key: str) -> str:
        """
        Function to upload the contents of a directory to a bucket.
        :param files: The files to be uploaded.
        :param root_dir: The root directory of the zip file.
        :param object_key: The key of the object in S3.
        :return: A S3 URI of the uploaded directory.
        """
        for file_path in files:
            relative_path = file_path.relative_to(root_dir)
            key = f"{object_key}/{relative_path.as_posix()}"
            try:
                self.s3.upload_file(
                    str(file_path),
                    self.bucket,
                    key,
                    ExtraArgs={"ContentType": extension_to_content_type(relative_path.suffix)}
                )
                logger.debug("Uploading '%s' to %s ", key, self.bucket)
            except ClientError as exc:
                logger.warning("Failed to upload '%s' to %s: %s", key, self.bucket, str(exc))
                continue

        return f"s3://{self.bucket}/{object_key}"

    def download_object(self, key, download_location: Union[PathLike, str]) -> None:
        """
        Function to download an object from S3 and save it to a temporary file.
        :param key: The key of the S3 object to download.
        :param download_location: The temp-file in which the object is saved.
        """
        try:
            self.s3.download_file(Bucket=self.bucket, Key=key, Filename=download_location)
        except ClientError as exc:
            logger.warning("Failed to download '%s' from %s: %s", key, self.bucket, str(exc))
            raise
