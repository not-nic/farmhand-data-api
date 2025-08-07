"""
Map Service Unit Tests.
"""

import random
from datetime import date

import pytest

from src.api.constants import ModHubMapFilters, FarmhandMapFilters
from src.api.core.db.models import Map
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModDetailModel
from src.api.services.map_service import MapService
from src.api.services.modhub_service import ModHubService


@pytest.mark.asyncio
@pytest.mark.usefixtures("db")
class TestMapService:
    @pytest.fixture
    def mod_detail(self):
        """
        Fixture specifying the return mod_detail object from the
        mocked mod_hub_service.
        """
        return ModDetailModel(
            id=123456,
            name="Custom Map 1",
            Game="FS25",
            Manufacturer="Lizard",
            Category="European Maps",
            Author="user",
            Size="30 MB",
            Version="1.0.0.0",
            Released="30.04.2025",
            Platform="PC/MAC",
            file_url="https://mod-download.com/custom-map-1.zip",
            zip_filename="custom-map-1.zip"
        )

    @pytest.fixture
    async def mock_mod_hub_service(self, mocker, mod_detail):
        """
        Mock the ModHUb service calls used within the map service with a
        single id and mod model.
        :param mocker: Pytest mocker fixture
        :param mod_detail: the mocked mod detail to return
        """

        mocker.patch.object(
            ModHubService,
            "scrape_mods",
            side_effect=[[123456]] + [[] for _ in range(len(ModHubMapFilters) - 1)],
        )

        mocker.patch.object(ModHubService, "get_pages", return_value=[0])
        mocker.patch.object(ModHubService, "scrape_mod", return_value=mod_detail)

    def test_get_all_maps(self, db):
        """
        Test that the map service can retrieve all map data from the
        repository.
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
        Test that the map service can get a saved map by its
        mod / map_id.
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
        Test that the map service can create a new map and
        save it in the database.
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

    def test_get_new_maps(self):
        pass

    def test_get_new_maps_with_no_new_maps(self):
        pass
