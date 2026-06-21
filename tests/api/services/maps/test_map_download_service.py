"""
Python module for testing the Map Download Service.
"""
import pytest
from botocore.exceptions import ClientError
from httpx2 import HTTPError

from src.api.services.maps.map_download_service import MapDownloadService


class TestMapDownloadService:
    """
    Unit tests for the map download service.
    """

    async def test_map_service_downloads_map(self, db, mod_detail, mock_mod_hub_service, mock_s3):
        """
        Test that the map service downloads a map from the ModHub and stores it within
        an S3 bucket.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        """

        s3_client, bucket = mock_s3
        map_download_service = MapDownloadService(mod_hub_service=mock_mod_hub_service)
        uri = await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)

        expected_object = s3_client.get_object(
            Bucket=bucket,
            Key=f"{mod_detail.id}/{mod_detail.zip_filename}",
        )

        assert expected_object is not None
        assert uri == f"s3://{bucket}/{mod_detail.id}/{mod_detail.zip_filename}"

    async def test_map_service_raises_http_error_when_download_fails(
        self,
        db,
        mod_detail,
        mock_mod_hub_service,
    ):
        """
        Test that the map service re-raises an HTTP error when communication
        with the ModHUb fails.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """

        mock_mod_hub_service.get_download_url.side_effect = HTTPError(
            "Unable to connect to the ModHub."
        )

        with pytest.raises(HTTPError):
            map_download_service = MapDownloadService()
            await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)

    async def test_map_service_raises_client_error_when_s3_upload_fails(
        self, mocker, db, mod_detail, mock_mod_hub_service
    ):
        """
        Test that the map service re-raises a ClientError error when communication
        with the AWS Service fails.
        :param mocker: Pytest mocker fixture.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_download_service = MapDownloadService(mod_hub_service=mock_mod_hub_service)

        client_error = ClientError(
            error_response={"Error": {"Code": "500", "Message": "Error uploading object"}},
            operation_name="PutObject",
        )

        mocker.patch.object(map_download_service.aws_service, "upload_object", side_effect=client_error)

        with pytest.raises(ClientError):
            await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)
