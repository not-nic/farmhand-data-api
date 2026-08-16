"""
Repository for Farmland database interactions.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from src.api.core.db.models.maps import Farmland
from src.api.core.repositories import Repository


class FarmlandRepository(Repository[Farmland]):
    """
    Repository class for managing farmlands.
    """

    def __init__(self, db: Session):
        super().__init__(db, Farmland)

    def get_by_map_and_number(self, map_id: int, number: int) -> Farmland | None:
        """
        Get a Farmland for a given map by its number.

        :param map_id: (int) The map ID to look up.
        :param number: (int) The farmland's number.
        :return: (Farmland) if it exists.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.map_id == map_id, self.model.number == number)
            .first()
        )

    def get_by_map_id(self, map_id: int) -> list[Farmland]:
        """
        Get all farmlands for a given Map ID.

        :param map_id: (int) The ID to retrieve farmlands for.
        :return: (list[Farmland]) a list of farmlands associated with the map.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).all()

    def get_pending_geometry(self) -> list[Farmland]:
        """
        Get farmlands that don't yet have coordinates extracted.

        :return: (list) of farmlands awaiting geometry extraction.
        """
        return self.db.query(self.model).filter(self.model.coordinates.is_(None)).all()

    def get_pending_environment(self) -> list[Farmland]:
        """
        Get farmlands that don't yet have an environment layer extracted.

        :return: (list) of farmlands awaiting geometry extraction.
        """
        return self.db.query(self.model).filter(self.model.area_types.is_(None)).all()

    def upsert(
        self,
        map_id: int,
        info_layer_id: UUID,
        number: int,
        price_per_ha: float | None = None,
        price_scale: float | None = None,
        default: bool = False,
    ) -> Farmland:
        """
        Upsert a Farmland for the given map and number.

        :param map_id: (int) The map ID to upsert a Farmland for.
        :param info_layer_id: (UUID) The farmlands InfoLayer this farmland belongs to.
        :param number: (int) The farmland's number.
        :param price_per_ha: (float) Price per hectare for farmland.
        :param price_scale: (float) The farmlands price multipliers.
        :param default: (bool) Whether this farmland starts owned.
        :return: (Farmland) The created or updated Farmland.
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
