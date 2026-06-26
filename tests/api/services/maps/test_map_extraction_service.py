"""
Python module containing unit tests for the Map Extraction Service.
"""
from zipfile import BadZipFile

import pytest

from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.schema.maps import MapModel
from src.api.services.maps.map_extraction_service import MapExtractionService
from src.api.services.maps.map_service import MapService


class TestMapExtractionService:
    """
    Unit tests for the Map Extraction Service.
    """

    async def test_map_service_extracts_files_from_mod_zip_file(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
            mock_s3,
            mock_file_parser_service,
    ):
        """
        Test that the map extraction service downloads a zip from S3, delegates
        parsing to the file parser, and re-uploads the restructured files.
        """
        client, bucket = mock_s3

        # Any bytes work here — extract_zip is mocked so the zip is never parsed.
        object_key = f"{mod_detail.id}/{mod_detail.zip_filename}"
        client.put_object(Bucket=bucket, Key=object_key, Body=b"fake-zip-content")

        map_service = MapService(db)
        map_obj = map_service.create_map(MapModel(**mod_detail.model_dump()))

        map_extraction_service = MapExtractionService(
            db,
            map_service=map_service,
            file_parser_service=mock_file_parser_service,
        )
        map_extraction_service.extract_map_files(map_obj)

        response = client.list_objects_v2(Bucket=bucket, Prefix=f"{map_obj.id}/")
        uploaded_files = {obj["Key"] for obj in response.get("Contents", [])}

        map_name = map_obj.zip_filename[:-4]
        expected_files = {
            f"{map_obj.id}/{map_obj.zip_filename}",
            f"{map_obj.id}/{map_name}/map/map.i3d",
            f"{map_obj.id}/{map_name}/config/vehicles.xml",
            f"{map_obj.id}/{map_name}/assets/overview.dds",
            f"{map_obj.id}/{map_name}/data/infoLayer.grle",
        }

        assert uploaded_files == expected_files
        assert map_service.get_map_by_id(map_obj.id).data_uri == f"s3://{bucket}/{map_obj.id}/{map_name}"

    async def test_map_service_raises_map_processing_error(
            self,
            db,
            mock_s3,
            mock_file_parser_service
    ):
        """
        Test that the map service captures a BadZipFile error
        and raises a 'MapProcessingError'.
        :param db: Database Session fixture.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """
        client, bucket = mock_s3
        object_key = "999999/bad.zip"
        client.put_object(Bucket=bucket, Key=object_key)

        mock_file_parser_service.extract_zip.side_effect = BadZipFile("Corrupted zip")
        map_obj = Map(id=999999, name="No File Map", zip_filename="bad.zip")

        map_extraction_service = MapExtractionService(db=db)

        with pytest.raises(MapProcessingError, match=f"Failed to process map '{map_obj.id}': File is not a zip file"):
            map_extraction_service.extract_map_files(map_obj)

    async def test_map_service_excepts_file_not_found(self, db, mock_s3, mock_file_parser_service):
        """
        Test that the map service captures a FileNotFound error
        and raises a 'MapProcessingError'.
        :param db: Database Session fixture.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """
        client, bucket = mock_s3
        object_key = "999999/no_file.zip"
        client.put_object(Bucket=bucket, Key=object_key)

        mock_file_parser_service.extract_zip.side_effect = FileNotFoundError("Missing file")

        map_extraction_service = MapExtractionService(db=db)
        map_obj = Map(id=999999, name="No File Map", zip_filename="no_file.zip")

        with pytest.raises(MapProcessingError, match=f"Failed to process map '{map_obj.id}': File is not a zip file"):
            map_extraction_service.extract_map_files(map_obj)
