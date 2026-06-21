"""
Map Service Unit Tests.
"""

from datetime import date

import pytest

from src.api.constants import FarmhandMapFilters
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.services.maps.map_service import MapService


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
            zip_filename="new_map_name.zip",
        )

        map_service = MapService(db)
        map_service.create_map(new_map)
        assert map_service.get_map_by_id(map_id) is not None

