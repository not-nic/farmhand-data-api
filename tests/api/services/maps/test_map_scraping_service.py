"""
Python module containing unit tests for the Map Scraping Service
"""

import pytest

from src.api.constants import FarmhandMapFilters, ModHubLabels, ModHubMapFilters
from src.api.core.db.models import Map
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModPreviewModel
from src.api.services.maps.map_scraping_service import MapScrapingService
from src.api.services.maps.map_service import MapService
from tests.utils import create_previews_by_category


class TestMapScrapingService:
    """
    Unit tests for the Map Scraping Service.
    """

    async def test_scrape_map_details(self, db, mod_detail, mock_mod_hub_service):
        """
        Test that the map service can scrape Map details and save them
        asserting it is the same object as the scraped mod.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_repository = MapRepository(db)

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        map_details = await map_scraping_service.scrape_map_details(mod_detail.id)

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
        mod_detail.category = "Prefab"

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        map_details = await map_scraping_service.scrape_map_details(mod_detail.id)

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
        map_service = MapService(db)
        map_service.create_map(MapModel(**mod_detail.model_dump()))

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        await map_scraping_service.scrape_map_details(mod_detail.id)

        expected_map: Map = map_repository.get_by_id(mod_detail.id)
        assert expected_map.version == mod_detail.version

    async def test_scrape_map_details_with_newer_version(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
    ):
        """
        Test that when an already saved map has a new version, it's re-scraped
        and updated.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_service = MapService(db)
        map_service.create_map(MapModel(**mod_detail.model_dump()))

        mod_detail.version = "1.1.0.0"

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        await map_scraping_service.scrape_map_details(mod_detail.id)

        expected_map: Map = map_service.get_map_by_id(mod_detail.id)
        assert expected_map.version != "1.0.0.0"

    async def test_check_new_maps_filters_out_prefabs(self, db, mock_mod_hub_service, mocker):
        """
        Test that when a prefab is found in a new map check, it is
        ignored and not counted as a new map.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mocker: Pytest mocker fixture.
        """
        mod_previews_by_category = create_previews_by_category(
            [
                (
                    ModPreviewModel(id=789013, name="Prefab Mod", label=ModHubLabels.PREFAB),
                    ModHubMapFilters.SOUTH_AMERICAN_MAPS,
                )
            ]
        )

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_scraping_service.check_for_new_maps()

        assert len(new_maps) == 0

    async def test_check_new_maps_appends_new_or_updated_maps(
            self,
            db,
            mock_mod_hub_service,
            mocker,
    ):
        """
        Test that when checking new maps new, updated and untagged maps
        that do not exist in the database are appended and returned.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mocker: Pytest mocker fixture.
        """
        mod_previews_by_category = create_previews_by_category(
            [
                (
                    ModPreviewModel(id=123456, name="European Map", label=ModHubLabels.NEW),
                    ModHubMapFilters.EUROPEAN_MAPS,
                ),
                (
                    ModPreviewModel(
                        id=456789, name="North American Map", label=ModHubLabels.UPDATE
                    ),
                    ModHubMapFilters.NORTH_AMERICAN_MAPS,
                ),
                (
                    ModPreviewModel(id=654321, name="Old Mod", label=ModHubLabels.UNTAGGED),
                    ModHubMapFilters.OTHER_MAPS,
                ),
            ]
        )

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_scraping_service.check_for_new_maps()

        assert len(new_maps) == 3

    @pytest.mark.parametrize("version, expected_new_maps", [("1.0.0.0", 0), ("1.1.0.0", 1)])
    async def test_check_new_maps_gets_details_if_already_exists(
            self,
            db,
            mod_detail,
            mock_mod_hub_service,
            mocker,
            version,
            expected_new_maps,
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

        mod_previews_by_category = create_previews_by_category(
            [
                (
                    ModPreviewModel(id=mod_detail.id, name=mod_detail.name, label=ModHubLabels.NEW),
                    ModHubMapFilters.EUROPEAN_MAPS,
                )
            ]
        )

        # Mock get_pages to return a single page for each filter
        mock_mod_hub_service.get_pages = mocker.AsyncMock(return_value=[1])

        # Mock scrape_mods to return the correct list based on category and page
        mock_mod_hub_service.scrape_mods = mocker.AsyncMock(
            side_effect=lambda category, page: mod_previews_by_category.get(category, [])
        )

        mod_detail.version = version

        map_scraping_service = MapScrapingService(db, mod_hub_service=mock_mod_hub_service)
        new_maps = await map_scraping_service.check_for_new_maps()

        assert len(new_maps) == expected_new_maps
