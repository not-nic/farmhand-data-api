"""
Map Service Unit Tests.
"""
from datetime import date
from zipfile import BadZipFile

import pytest
from botocore.exceptions import ClientError
from httpx import HTTPError

from src.api.constants import FarmhandMapFilters, ModHubLabels, ModHubMapFilters
from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModPreviewModel
from src.api.services.map_service import MapService
from tests.utils import create_previews_by_category, create_test_zip_file


@pytest.mark.asyncio
@pytest.mark.usefixtures("db")
class TestMapService:

    def test_get_all_maps(self, db):
        """
        Test that the map service can retrieve all map data from the repository.
        :param db: Database Session fixture.
        """
        map_repository = MapRepository(db)

        map_repository.create(
            id=1,
            name="Custom Farms",
            category="European Maps",
            author="user",
            release_date="30-04-2025",
            version="1.0.0.0",
        )

        map_repository.create(
            id=2,
            name="Custom Farms 2",
            category="European Maps",
            author="user2",
            release_date="07-08-2025",
            version="1.0.3.0",
        )

        map_service = MapService(db)
        assert len(map_service.get_maps()) == 2

    def test_get_map_by_id(self, db):
        """
        Test that the map service can get a saved map by its mod / map_id.
        :param db: Database Session Fixture.
        """
        map_id: int = 123456
        map_repository = MapRepository(db)

        map_repository.create(
            id=map_id,
            name="Custom Farms",
            category="European Maps",
            author="user",
            release_date="30-04-2025",
            version="1.0.0.0",
        )

        map_service = MapService(db)
        assert map_service.get_map_by_id(map_id) is not None

    def test_create_map(self, db):
        """
        Test that the map service can create a new map and save it in the database.
        :param db: Database Session Fixture.
        """
        map_id: int = 999999
        new_map = MapModel(
            id=map_id,
            name="New Map Name",
            category=FarmhandMapFilters.EUROPEAN_MAPS,
            author="Nicholas Angel",
            release_date=date(day=7, month=8, year=2025),
            version="1.0.1.0",
            zip_filename="new_map_name.zip"
        )

        map_service = MapService(db)
        map_service.create_map(new_map)
        assert map_service.get_map_by_id(map_id) is not None

    async def test_get_new_maps(
            self,
            mocker,
            db,
            mod_detail,
            mock_mod_hub_service,
            mock_s3,
            mock_file_parser_service
    ):
        """
        Test that the map service gets new maps, uploads them to S3, extracts files
        and saves them to the database.
        :param mocker: Pytest mocker fixture.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        :return:
        """
        map_service = MapService(
            db,
            mod_hub_service=mock_mod_hub_service,
            file_parser_service=mock_file_parser_service,
        )

        # Mock the check for new maps response.
        mocker.patch.object(
            map_service,
            "check_for_new_maps",
            new=mocker.AsyncMock(return_value=[
                ModPreviewModel(id=123456, name="Custom Map 1", label=ModHubLabels.NEW),
                ModPreviewModel(id=456789, name="Custom Map 2", label=ModHubLabels.NEW),
            ])
        )

        # Mock the ModHub service scrape_mod response with ModDetail models.
        mocker.patch.object(
            map_service.mod_hub_service,
            "scrape_mod",
            new=mocker.AsyncMock(side_effect=[
                mod_detail.model_copy(
                    update={
                        "id": 123456,
                        "name": "Custom Map 1",
                        "category": "map_europe",
                        "Version": "1.0.0.0"
                    }),
                mod_detail.model_copy(
                    update={
                        "id": 456789,
                        "name": "Custom Map 2",
                        "category": "map_europe",
                        "Version": "1.0.0.0"
                    }
                )
            ]),
        )

        # ignore the download and extracting files
        mocker.patch.object(map_service, "download_map", new=mocker.AsyncMock(return_value=None))
        mocker.patch.object(map_service, "extract_map_files", return_value=None)

        # assert two mods were added to the databse.
        await map_service.get_new_maps()
        assert len(map_service.get_maps()) == 2

    async def test_get_new_maps_with_no_new_maps(self, db, mock_mod_hub_service):
        """
        Test get new maps when no new or updated maps are available.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        await map_service.get_new_maps()
        map_repository = MapRepository(db)
        assert len(map_repository.all()) == 0

    async def test_scrape_map_details(self, db, mod_detail, mock_mod_hub_service):
        """
        Test that the map service can scrape Map details and save them
        asserting it is the same object as the scraped mod.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_repository = MapRepository(db)
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        map_details = await map_service.scrape_map_details(mod_detail.id)

        # Assert that the map was added to the DB.
        assert len(map_repository.all()) == 1

        # Assert the details of the mod match the created map details
        assert mod_detail.id == map_details.id
        assert mod_detail.name == map_details.name
        assert mod_detail.author == map_details.author
        assert mod_detail.version == map_details.version
        assert str(mod_detail.release_date) == map_details.release_date
        assert mod_detail.zip_filename == map_details.zip_filename

        # Assert that the filter has been changed to a 'farmhand filter'
        assert map_details.category == FarmhandMapFilters.EUROPEAN_MAPS

    async def test_scrape_map_details_with_prefab(self, db, mod_detail, mock_mod_hub_service):
        """
        Test that when the map service finds a 'Prefab' it is ignored
        and None is returned by the 'scrape_map_details' method.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        mod_detail.category = "Prefab"

        map_details = await map_service.scrape_map_details(mod_detail.id)

        assert map_details is None

    async def test_scrape_map_details_with_same_version(self, db, mod_detail, mock_mod_hub_service):
        """
        Test that if a map is already created and the same version is scraped
        again, no changes are made to the current map.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_repository = MapRepository(db)
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        map_service.create_map(MapModel(**mod_detail.model_dump()))

        await map_service.scrape_map_details(mod_detail.id)

        expected_map: Map = map_repository.get_by_id(mod_detail.id)
        assert expected_map.version == mod_detail.version

    async def test_scrape_map_details_with_newer_version(self, db, mod_detail, mock_mod_hub_service):
        """
        Test that when an already saved map has a new version, it's re-scraped
        and updated.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_repository = MapRepository(db)
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        map_service.create_map(MapModel(**mod_detail.model_dump()))

        mod_detail.version = "1.1.0.0"

        await map_service.scrape_map_details(mod_detail.id)

        expected_map: Map = map_repository.get_by_id(mod_detail.id)
        assert expected_map.version != "1.0.0.0"

    async def test_check_new_maps_filters_out_prefabs(self, db, mock_mod_hub_service, mocker):
        """
        Test that when a prefab is found in a new map check, it is
        ignored and not counted as a new map.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mocker: Pytest mocker fixture.
        """
        mod_previews_by_category = create_previews_by_category([
            (
                ModPreviewModel(id=789013, name="Prefab Mod", label=ModHubLabels.PREFAB),
                ModHubMapFilters.SOUTH_AMERICAN_MAPS
            )
        ])

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_service.check_for_new_maps()

        assert len(new_maps) == 0

    async def test_check_new_maps_appends_new_or_updated_maps(self, db, mock_mod_hub_service, mocker):
        """
        Test that when checking new maps new, updated and untagged maps
        that do not exist in the database are appended and returned.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mocker: Pytest mocker fixture.
        """
        mod_previews_by_category = create_previews_by_category([
            (
                ModPreviewModel(id=123456, name="European Map", label=ModHubLabels.NEW),
                ModHubMapFilters.EUROPEAN_MAPS
            ),
            (
                ModPreviewModel(id=456789, name="North American Map", label=ModHubLabels.UPDATE),
                ModHubMapFilters.NORTH_AMERICAN_MAPS
            ),
            (
                ModPreviewModel(id=654321, name="Old Mod", label=ModHubLabels.UNTAGGED),
                ModHubMapFilters.OTHER_MAPS,
            )
        ])

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_service.check_for_new_maps()

        assert len(new_maps) == 3

    @pytest.mark.parametrize("version, expected_new_maps", [("1.0.0.0", 0), ("1.1.0.0", 1)])
    async def test_check_new_maps_gets_details_if_already_exists(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
            mocker,
            version,
            expected_new_maps
    ):
        """
        Test that when checking for new maps, if the map already
        exists, it scrapes the mod details to determine if the version
        needs updating.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mocker: Pytest mocker fixture.
        :param version: The new version of the map.
        :param expected_new_maps: The expected number of 'new' maps to be returned.
        """

        map_service = MapService(db)
        map_service.create_map(MapModel(**mod_detail.model_dump()))

        mod_previews_by_category = create_previews_by_category([
            (
                ModPreviewModel(id=mod_detail.id, name=mod_detail.name, label=ModHubLabels.NEW),
                ModHubMapFilters.EUROPEAN_MAPS
            )
        ])

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        mod_detail.version = version

        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_service.check_for_new_maps()

        assert len(new_maps) == expected_new_maps

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
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
        uri = await map_service.download_map(mod_detail.id, mod_detail.zip_filename)

        expected_object = s3_client.get_object(
            Bucket=bucket,
            Key=f"{mod_detail.id}/{mod_detail.zip_filename}"
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

        mock_mod_hub_service.get_download_url.side_effect = HTTPError("Unable to connect to the ModHub.")

        with pytest.raises(HTTPError):
            map_service = MapService(db, mod_hub_service=mock_mod_hub_service)
            await map_service.download_map(mod_detail.id, mod_detail.zip_filename)

    async def test_map_service_raises_client_error_when_s3_upload_fails(
            self,
            mocker,
            db,
            mod_detail,
            mock_mod_hub_service
    ):
        """
        Test that the map service re-raises a ClientError error when communication
        with the AWS Service fails.
        :param mocker: Pytest mocker fixture.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_service = MapService(db, mod_hub_service=mock_mod_hub_service)

        client_error = ClientError(error_response={"Error": {
                    "Code": "500",
                    "Message": "Error uploading object"
                }
            },
            operation_name="PutObject"
        )

        mocker.patch.object(
            map_service.aws_service,
            "upload_object",
            side_effect=client_error
        )

        with pytest.raises(ClientError):
            await map_service.download_map(mod_detail.id, mod_detail.zip_filename)

    async def test_map_service_extracts_files_from_mod_zip_file(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
            mock_s3,
            mock_file_parser_service
    ):
        """
        Test that the map service can extract files from a 'zip' archive
        stored within S3, refactor the files into a standard format and re-upload them.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """

        # create a zip archive in the S3 mock.
        client, bucket = mock_s3
        zip_content = create_test_zip_file([
            "map.i3d", "vehicles.xml", "overview.dds", "infoLayer.grle"
        ])

        object_key = f"{mod_detail.id}/{mod_detail.zip_filename}"
        client.put_object(Bucket=bucket, Key=object_key, Body=zip_content)

        map_service = MapService(
            db=db,
            mod_hub_service=mock_mod_hub_service,
            file_parser_service=mock_file_parser_service
        )

        map_service.create_map(MapModel(**mod_detail.model_dump()))
        map_service.extract_map_files(mod_detail.id, mod_detail.zip_filename)

        # Get the unzipped files from S3.
        response = client.list_objects_v2(Bucket=bucket, Prefix=f"{mod_detail.id}/")
        uploaded_files = {obj["Key"] for obj in response.get("Contents", [])}

        # remove .zip to get the unzipped map name.
        map_name = mod_detail.zip_filename[:-4]

        expected_files = {
            f"{mod_detail.id}/{mod_detail.zip_filename}",
            f"{mod_detail.id}/{map_name}/map/map.i3d",
            f"{mod_detail.id}/{map_name}/config/vehicles.xml",
            f"{mod_detail.id}/{map_name}/assets/overview.dds",
            f"{mod_detail.id}/{map_name}/data/infoLayer.grle"
        }

        # assert the correct files have been uploaded to the bucket in the correct format.
        assert uploaded_files == expected_files

        map_repository = MapRepository(db)
        expected_map: Map = map_repository.get_by_id(mod_detail.id)

        assert expected_map.data_uri == f"s3://{bucket}/{mod_detail.id}/{map_name}"

    async def test_map_service_raises_map_processing_error(self, db, mock_s3, mock_file_parser_service):
        """
        Test that the map service captures a BadZipFile error
        and raises a 'MapProcessingError'.
        :param db: Database Session fixture.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """
        client, bucket = mock_s3
        object_key = f"999999/bad.zip"
        client.put_object(Bucket=bucket, Key=object_key)

        mock_file_parser_service.extract_zip.side_effect = BadZipFile("Corrupted zip")

        service = MapService(
            db=db,
            file_parser_service=mock_file_parser_service
        )

        with pytest.raises(MapProcessingError, match="Failed to process map data"):
            service.extract_map_files(999999, "bad.zip")

    async def test_map_service_excepts_file_not_found(self, db, mock_s3, mock_file_parser_service):
        """
        Test that the map service captures a FileNotFound error
        and raises a 'MapProcessingError'.
        :param db: Database Session fixture.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """
        client, bucket = mock_s3
        object_key = f"999999/no_file.zip"
        client.put_object(Bucket=bucket, Key=object_key)

        mock_file_parser_service.extract_zip.side_effect = FileNotFoundError("Missing file")

        service = MapService(
            db=db,
            file_parser_service=mock_file_parser_service
        )

        with pytest.raises(MapProcessingError, match="Failed to process map data"):
            service.extract_map_files(999999, "no_file.zip")
