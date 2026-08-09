"""
Repository for Farmland database interactions.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.maps import Farmland
from src.api.core.repositories import Repository


class FarmlandRepository(Repository[Farmland]):
    """
    Repository for Farmland database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, Farmland)

    def get_by_map_and_number(self, map_id: int, number: int) -> Farmland | None:
        """
        Get a Farmland for a given map by its number.

        :param map_id: The map ID to look up.
        :param number: The farmland's number, matching the i3d Option value.
        :return: Farmland if it exists, else None.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.map_id == map_id, self.model.number == number)
            .first()
        )

    def get_by_map_id(self, map_id: int) -> list[Farmland]:
        """
        Get all farmlands for a given Map ID.

        :param map_id: the ID to retrieve farmlands for.
        :return: (list[Farmland])a list of farmlands associated with the map.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).all()

    def get_pending_geometry(self) -> list[Farmland]:
        """
        Get farmlands that don't yet have coordinates extracted.

        :return: List of farmlands awaiting geometry extraction.
        """
        return self.db.query(self.model).filter(self.model.coordinates.is_(None)).all()

    def get_pending_area_types(self) -> list[Farmland]:
        """
        Get farmlands that don't yet have area types extracted.

        :return: List of farmlands awaiting geometry extraction.
        """
        return self.db.query(self.model).filter(self.model.area_types.is_(None)).all()

    def upsert(
        self,
        map_id: int,
        info_layer_id,
        number: int,
        price_per_ha: float | None = None,
        price_scale: float | None = None,
        default: bool = False,
    ) -> Farmland:
        """
        Create or update a Farmland for the given map and number.
        :param map_id: The map ID to upsert a Farmland for.
        :param info_layer_id: The farmlands InfoLayer this farmland belongs to.
        :param number: The farmland's number, matching the i3d Option value.
        :param price_per_ha: Map-wide price per hectare from farmlands.xml.
        :param price_scale: This farmland's price multipliers from farmlands.xml.
        :param default: Whether this farmland starts owned.
        :return: The created or updated Farmland.
        """
        existing = self.get_by_map_and_number(map_id, number)

        if existing:
            return self.update(
                existing,
                price_per_ha=price_per_ha,
                price_scale=price_scale,
                default=default,
            )

        return self.create(
            map_id=map_id,
            info_layer_id=info_layer_id,
            number=number,
            price_per_ha=price_per_ha,
            price_scale=price_scale,
            default=default,
        )
