"""
Repository for MapVehicle database interactions.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.maps.map_vehicle import MapVehicle
from src.api.core.repositories import Repository


class MapVehicleRepository(Repository[MapVehicle]):
    """
    Repository for MapVehicle database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, MapVehicle)

    def get_by_map_id(self, map_id: int) -> list[MapVehicle]:
        """
        Get all starting vehicles for a given map.
        :param map_id: The map ID to look up.
        :return: List of MapVehicle, empty if the map has none.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).all()

    def replace_for_map(self, map_id: int, vehicles: list[MapVehicle]) -> list[MapVehicle]:
        """
        Replace all starting vehicles of a map.
        :param map_id: The map to update, set on each new row.
        :param vehicles: New MapVehicle rows, map_id is assigned here.
        :return: The newly created MapVehicle rows.
        """
        self.db.query(self.model).filter(self.model.map_id == map_id).delete()
        for vehicle in vehicles:
            vehicle.map_id = map_id
        self.db.add_all(vehicles)
        self.db.commit()
        return vehicles
