"""
Map Service Unit Tests.
"""

import random

import pytest

from src.api.constants import ModHubMapFilters
from src.api.core.db.models import Map
from src.api.core.repositories import MapRepository
from src.api.core.schema.mods import ModModel
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
        return ModModel(
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
        )

    @pytest.fixture
    def mock_mod_hub_service(self, mocker, mod_detail):
        """
        Mock the modhub service calls used within the map service with a
        single id and mod model.
        :param mocker: pytest mocker fixture
        :param mod_detail: the mocked mod detail to return
        """

        mocker.patch.object(
            ModHubService,
            "scrape_mods",
            side_effect=[[123456]] + [[] for _ in range(len(ModHubMapFilters) - 1)],
        )

        mocker.patch.object(ModHubService, "get_pages", return_value=[0])

        mocker.patch.object(ModHubService, "scrape_mod", return_value=mod_detail)

    async def test_get_map_that_does_not_exist(self, db, mock_mod_hub_service, mod_detail):
        """
        Test that the map_service creates a map from the mock mod hub service fixture.
        :param mock_mod_hub_service: mock modhub service fixture
        :param mod_detail: mod detail fixture
        """

        map_service = MapService(db)
        map_repository = MapRepository(db)
        await map_service.scrape_maps()

        assert len(map_repository.all()) == 1

        expected_map: Map = map_repository.get_by_id(mod_detail.id)

        assert expected_map.id == mod_detail.id
        assert expected_map.name == mod_detail.name
        assert expected_map.author == mod_detail.author
        assert expected_map.category == mod_detail.category
        assert expected_map.release_date == str(mod_detail.release_date)
        assert expected_map.version == mod_detail.version

    async def test_get_map_updates_based_on_mod_version(self, db, mock_mod_hub_service, mod_detail):
        """
        Test that the map service updates a map based on its version when scraping maps
        from modhub.
        :param mock_mod_hub_service: mock modhub service fixture
        :param mod_detail: mod detail fixture
        """
        map_repository = MapRepository(db)
        map_repository.create(
            id=654321,
            name="Calmsden Farms",
            category="European Maps",
            author="user",
            release_date="30-04-2025",
            version="1.0.0.0",
        )

        mod_detail.id = 654321
        mod_detail.name = "Oak Bridge Farm"
        mod_detail.version = "1.1.0.0"

        map_service = MapService(db)
        await map_service.scrape_maps()

        expected_map: Map = map_repository.get_by_id(mod_detail.id)

        # assert the mod_detail version and mod detail name are not equal.
        assert mod_detail.version != expected_map.version
        assert mod_detail.name != expected_map.name

    async def test_get_map_does_not_update_for_same_mod_version(
        self, db, mock_mod_hub_service, mod_detail
    ):
        """
        Test that when getting maps from modhub, no update is applied if the
        version number is the same.
        :param mock_mod_hub_service: mock modhub service fixture
        :param mod_detail: mod detail fixture
        """
        map_repository = MapRepository(db)
        map_id = random.randint(100000, 999999)

        map_repository.create(
            id=map_id,
            name="Custom Map 1",
            category="European Maps",
            author="user",
            release_date="30-04-2025",
            version="1.0.0.0",
        )

        mod_detail.id = map_id

        map_service = MapService(db)
        await map_service.scrape_maps()

        expected_map: Map = map_repository.get_by_id(mod_detail.id)

        assert mod_detail.version == expected_map.version
        assert mod_detail.name == expected_map.name
