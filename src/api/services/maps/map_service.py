"""
Map Service Module currently used for manually scraping map data
when new maps are released.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.db.models import Map
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel


class MapService:
    """
    Map Service used for getting map information from the ModHub
    and creating map entries in the database.
    """

    def __init__(self, db: Session):
        """
        Constructor for the map service.
        :param db: Database Session.
        """
        self.map_repository = MapRepository(db)

    def get_maps(self) -> list[Map]:
        """
        Get all maps.
        :return: List of maps.
        """
        return self.map_repository.all()

    def get_map_by_id(self, map_id: int) -> Map | None:
        """
        Get a map by its ModHub ID.
        :return: (Optional) the map if it exists.
        """
        return self.map_repository.get_by_id(map_id)

    def get_maps_by_status(self, status: IngestionStatus) -> list[Map]:
        """
        Retrieve a list of maps for a given ingestion status enum, e.g. PENDING, DOWNLOADED.
        :param status: The ingestion status to retrieve.
        :return: (list) A list of maps with a matching status.
        """
        return self.map_repository.get_by_status(status)

    def create_map(self, map_obj: MapModel) -> Map:
        """
        Create a map in the database from its pydantic MapModel.
        :param map_obj: MapModel attributes to create a map.
        :return: The created map object.
        """
        return self.map_repository.create(**map_obj.model_dump())

    def update_map(self, map_obj: Map, **fields) -> Map:
        """
        Update a map in the database with the given fields.
        :param map_obj: The map instance to update.
        :param fields: Fields to update, e.g. update_map(map, data_uri="...")
        :return: The updated map object.
        """
        return self.map_repository.update(map_obj, **fields)

    def get_maps_with_data_uri(self) -> list[Map]:
        """
        Get all maps that have extracted data uploaded.
        """
        return self.map_repository.get_with_data_uri()

    def get_stalled_maps(self, status: IngestionStatus, stalled_before: datetime) -> list[Map]:
        """
        Gets all stalled maps from the repository.
        :param status: (IngestionStatus) The ingestion stage.
        :param stalled_before: (datetime) a datetime value to decide what's 'stalled'.
        :return: List of stalled maps.
        """
        return self.map_repository.get_stalled(status, stalled_before)
