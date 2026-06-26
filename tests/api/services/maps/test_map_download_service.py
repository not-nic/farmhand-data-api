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

    async def test_map_service_downloads_map(
            self,
            db,
            mocker,
            mod_detail,
            mock_mod_hub_service,
            mock_s3
    ):
        """
        Test that the map download service retrieves a download URL, streams the
        mod from ModHub, and uploads it to S3 via upload_stream.
        """
        s3_client, bucket = mock_s3
        expected_uri = f"s3://{bucket}/{mod_detail.id}/{mod_detail.zip_filename}"
        map_download_service = MapDownloadService(mod_hub_service=mock_mod_hub_service)

        # Mock the streaming upload and patch the existing URI.
        mocker.patch.object(
            map_download_service.aws_service,
            "upload_stream",
            return_value=expected_uri,
        )
        mocker.patch.object(
            map_download_service.aws_service,
            "get_object_size",
            return_value=512 * 1024 * 1024
        )

        uri = await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)

        mock_mod_hub_service.get_download_url.assert_called_once_with(mod_id=mod_detail.id)
        mock_mod_hub_service.download_mod_stream.assert_called_once()
        assert uri == expected_uri

    async def test_map_service_raises_http_error_when_download_fails(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
    ):
        """
        Test that the map download service re-raises an HTTPError when
        communication with the ModHub fails.
        """
        mock_mod_hub_service.get_download_url.side_effect = HTTPError(
            "Unable to connect to the ModHub."
        )

        with pytest.raises(HTTPError):
            map_download_service = MapDownloadService(mod_hub_service=mock_mod_hub_service)
            await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)

    async def test_map_service_raises_client_error_when_s3_upload_fails(
            self, mocker, db, mod_detail, mock_mod_hub_service
    ):
        """
        Test that the map download service re-raises a ClientError when the
        S3 upload fails.
        """
        map_download_service = MapDownloadService(mod_hub_service=mock_mod_hub_service)

        client_error = ClientError(
            error_response={"Error": {"Code": "500", "Message": "Error uploading object"}},
            operation_name="PutObject",
        )

        mocker.patch.object(
            map_download_service.aws_service,
            "upload_stream",
            side_effect=client_error,
        )

        with pytest.raises(ClientError):
            await map_download_service.download_map(mod_detail.id, mod_detail.zip_filename)
