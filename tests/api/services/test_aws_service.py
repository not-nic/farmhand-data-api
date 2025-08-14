# python
"""
Module containing unit tests for the AWS Service
"""

from typing import Literal
from urllib.parse import parse_qs, urlparse

import pytest
from botocore.exceptions import ClientError

from src.api.services.aws_service import AwsService


class TestAwsService:
    @pytest.fixture
    def sample_files(self, tmp_path):
        """
        Create a temporary directory with a single XML file and root directory.
        :param tmp_path: Temp path fixture.
        :return: (tuple) of a root directory and list of 'files'.
        """
        root_dir = tmp_path / "map"
        (root_dir / "config").mkdir(parents=True, exist_ok=True)

        xml_file = root_dir / "config" / "config.xml"
        xml_file.write_text("<config><value>123</value></config>")

        return root_dir, [xml_file]

    @pytest.fixture
    def mock_s3_error(self):
        """
        Fixture containing a mock boto3 client error.
        :return: A 500 ClientError
        """
        return ClientError(
            error_response={"Error": {"Code": "500", "Message": "Error uploading object"}},
            operation_name="PutObject",
        )

    @pytest.mark.parametrize("method_type", ["get_object", "put_object"])
    def test_generate_pre_signed_url(
            self,
            mock_s3,
            method_type: Literal["get_object", "put_object"]
    ):
        """
        Test that a pre-signed GET and PUT url can be generated
        and assert that the standard parameters exist in the generated
        URL.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param method_type: Parameter for a get and put object.
        """
        aws_service = AwsService()

        key = "test.txt"
        url = aws_service.generate_pre_signed_url(key, method_type, 300)

        assert isinstance(url, str)
        assert key in url

        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        expected_params = [
            "X-Amz-Algorithm",
            "X-Amz-Credential",
            "X-Amz-Date",
            "X-Amz-Expires",
            "X-Amz-Signature"
        ]

        for param in expected_params:
            assert param in query

    def test_generate_pre_signed_url_raises_client_error(self, mocker, mock_s3):
        """
        Test that the aws_service raises a ClientError when a pre-signed URL
        cannot be generated.
        :param mocker: Pytest mocker fixture.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        """
        client_error = ClientError(
            error_response={
                "Error": {
                    "Code": "500",
                    "Message": "Error uploading object",
                }
            },
            operation_name="PutObject",
        )

        aws_service = AwsService()
        mocker.patch.object(aws_service.s3, "generate_presigned_url", side_effect=client_error)

        with pytest.raises(ClientError, match="Error uploading object"):
            aws_service.generate_pre_signed_url("test.txt", "put_object", 300)

    def test_upload_file_object(self, mock_s3):
        """
        Test the aws_service can upload a file-like object, and it can be
        retrieved by the mock S3 client.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        """

        client, bucket = mock_s3

        mod_id: int = 123456
        file_name: str = "file.zip"
        data = b"hello world"

        aws_service = AwsService()
        aws_service.upload_object(data, mod_id, file_name)

        response = client.get_object(Bucket=bucket, Key=f"{mod_id}/{file_name}")
        body = response["Body"].read()
        assert body == data

    def test_upload_file_object_raises_client_error(self, mock_s3):
        """
        Test the aws_service raises a ClientError when an invalid
        file is uploaded.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        """

        with pytest.raises(ClientError):
            aws_service = AwsService(bucket_name="non-existent-bucket")
            aws_service.upload_object(b"content", 123456, "file.zip")

    def test_upload_directory_contents(self, mock_s3, sample_files):
        """
        Test the aws_service can upload the contents of a directory
        and keep the same file paths.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param sample_files: Fixture containing sample files to upload.
        """
        client, bucket = mock_s3
        root_dir, files = sample_files

        object_key = "123456/map_directory"
        aws_service = AwsService()
        uri = aws_service.upload_directory_contents(
            files=files, root_dir=root_dir, object_key=object_key
        )

        assert uri == f"s3://{bucket}/{object_key}"

        response = client.list_objects_v2(Bucket=bucket, Prefix=object_key)
        objects = response.get("Contents", [])
        assert len(objects) == 1

    def test_upload_directory_contents_raises_error(
            self,
            mocker,
            mock_s3,
            sample_files,
            mock_s3_error
    ):
        """
        Test the aws_service raises a client error when failing to upload
        the contents of a directory.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param sample_files: Fixture containing sample files to upload.
        :param mock_s3_error: Fixture containing a fake Boto3 Client Error.
        """
        root_dir, files = sample_files

        aws_service = AwsService()
        mocker.patch.object(
            aws_service.s3, "upload_file", side_effect=mock_s3_error
        )

        with pytest.raises(ClientError, match="Error uploading object"):
            aws_service.upload_directory_contents(
                files=files, root_dir=root_dir, object_key="123456/map_directory"
            )

    def test_download_file_object(self, mock_s3, tmp_path):
        """
        Test the aws_service can download a file from a bucket and store it in a
        file location.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param tmp_path: Temp path fixture.
        """
        client, bucket = mock_s3
        aws_service = AwsService()

        key = "test.txt"
        client.put_object(Bucket=bucket, Key=key, Body=b"dummy content")

        dest_path = tmp_path / key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        aws_service.download_object(key, dest_path)

        file_count = sum(1 for p in tmp_path.rglob("*") if p.is_file())
        assert file_count == 1
        assert dest_path.read_bytes() == b"dummy content"

    def test_download_file_object_raises_client_error(self, mock_s3, tmp_path):
        """
        Test the aws_service raises a client error when failing to download
        an object from S3.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param tmp_path: Temp path fixture.
        """
        aws_service = AwsService()

        with pytest.raises(ClientError):
            aws_service.download_object("123456/not-a-map.zip", "location")
