"""
Python module containing a MapBuilderService used to generate map information
from infoLayer, and i3d data to build up a farming simulator 'map'.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from src.api.builder.map_builder import MapBuilder
from src.api.constants import IngestionStatus
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.services.maps.map_service import MapService


class MapBuilderService:
    """
    Service class to process maps that have not yet had map data extracted
    from them.
    """

    def __init__(self, db: Session) -> None:
        self.map_service = MapService(db)
        self.map_builder = MapBuilder(db)

    def process_pending(self) -> None:
        """
        Method to process pending maps that have not been ingested yet.
        """
        map_ids = self.map_builder.get_pending_map_ids()

        if not map_ids:
            return

        for map_id in map_ids:
            self._process_map(map_id)

    def _process_map(self, map_id: int) -> None:
        """
        Get and build map data for a given map.

        :param map_id: (int) The map to process.
        """
        map_obj: Map | None = self.map_service.get_map_by_id(map_id)

        if not map_obj:
            logger.warning("[MapBuilderService]: Map %d not found — skipping.", map_id)
            return

        if map_obj.ingestion_status == IngestionStatus.FAILED:
            logger.debug(
                "[MapBuilderService]: Skipping map %d — ingestion status is FAILED.", map_id
            )
            return

        errors = self.map_builder.build(map_obj)
        self._update_ingestion_result(map_obj, errors)

    def _update_ingestion_result(self, map_obj: Map, errors: list[str]) -> None:
        """
        Util method to update the map as failed, if any infoLayer builder failed.

        :param map_obj: (Map) The map whose ingestion status is being recorded.
        :param errors: (list[str]) Error messages collected from builder failures
        """
        if not errors:
            return

        self.map_service.update_map(
            map_obj,
            ingestion_status=IngestionStatus.FAILED,
            ingestion_error="; ".join(errors),
            ingestion_updated_at=datetime.now(),
        )

        logger.error(
            "[MapBuilderService]: Marked '%s' (%d) as FAILED after %d builder error(s).",
            map_obj.name,
            map_obj.id,
            len(errors),
        )

