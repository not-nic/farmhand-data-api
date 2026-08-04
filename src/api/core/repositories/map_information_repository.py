"""
Repository for MapInformation database interactions.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.maps.map_information import MapInformation
from src.api.core.repositories import Repository


class MapInformationRepository(Repository[MapInformation]):
    """
    Repository for MapInformation database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, MapInformation)

    def get_by_map_id(self, map_id: int) -> MapInformation | None:
        """
        Get the map information for a given map ID.
        :param map_id: The map ID to look up.
        :return: MapInformation if it exists, else None.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).first()

    def upsert(self, map_id: int, **kwargs) -> MapInformation:
        """
        Upsert map information with new or updated data.
        :param map_id: (int) a given map to update.
        :param kwargs: Additional arguments for the MapInformation model.
        :return: A created or updated MapInformation model.
        """
        existing = self.get_by_map_id(map_id)
        if existing:
            return self.update(existing, **kwargs)
        return self.create(map_id=map_id, **kwargs)
