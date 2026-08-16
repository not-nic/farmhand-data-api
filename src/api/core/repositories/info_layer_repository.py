"""
Repository for MapInfoLayer database interactions.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.maps import InfoLayer
from src.api.core.repositories import Repository


class InfoLayerRepository(Repository[InfoLayer]):
    """
    Repository for MapInfoLayer database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, InfoLayer)

    def get_pending(self) -> list[InfoLayer]:
        """
        Get assets registered but not yet converted and uploaded.

        :return: (list) of assets that are not ingested.
        """
        query = self.db.query(self.model).filter(self.model.is_ingested.is_(False))
        return query.all()

    def get_by_map_id(self, map_id: int) -> list[InfoLayer]:
        """
        Get all info layers for a given map.

        :param map_id: (int) The map ID to look up.
        :return: (list) of info layers belonging to the map.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).all()

    def get_by_map_and_key(self, map_id: int, layer_key: str) -> InfoLayer | None:
        """
        Get a MapInfoLayer for a given map by its layer_key.

        :param map_id: (int) The map ID to look up.
        :param layer_key: (str) The InfoLayer name, e.g. 'farmlands' or 'soilMap'.
        :return: (MapInfoLayer) if it exists.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.map_id == map_id, self.model.layer_key == layer_key)
            .first()
        )

    def upsert(
            self,
            map_id: int,
            layer_key: str,
            grle_filename: str | None = None,
            i3d_file_id: str | None = None,
    ) -> InfoLayer:
        """
        Upsert the InfoLayer for the given map and layer_key.

        :param map_id: (int) The map ID to upsert an InfoLayer for.
        :param layer_key: (str) The InfoLayer name, e.g. 'farmlands' or 'soilMap'.
        :param grle_filename: (str) Filename of the source GRLE.
        :param i3d_file_id: (str) fileId referenced in map.i3d for this layer.
        :return: (InfoLayer) The created or updated InfoLayer.
        """
        existing = self.get_by_map_and_key(map_id, layer_key)

        if existing:
            return self.update(
                existing,
                grle_filename=grle_filename,
                i3d_file_id=i3d_file_id,
            )

        return self.create(
            map_id=map_id,
            layer_key=layer_key,
            grle_filename=grle_filename,
            i3d_file_id=i3d_file_id,
        )
