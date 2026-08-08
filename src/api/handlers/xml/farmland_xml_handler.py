"""
Python module containing a handler for a map's farmlands.xml file.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.core.schema.maps.farmlands import FarmlandsXmlModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.farmland_xml_parser import FarmlandsXmlParser
from src.api.services.aws.aws_service import AwsService

_FARMLANDS_LAYER_KEY = "farmlands"


class FarmlandsXmlHandler(BaseXmlHandler[FarmlandsXmlModel]):
    """
    Processes a map's farmlands.xml file into Farmland rows. coordinates
    and size_ha are left null until the geometry extraction job runs.
    """

    def __init__(
        self,
        db: Session,
        aws_service: AwsService,
    ) -> None:
        super().__init__(db, aws_service)
        self.info_layer_repository = InfoLayerRepository(db)
        self.farmland_repository = FarmlandRepository(db)

    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and store farmlands for the given map.

        :param map_obj: The map to process.
        """
        if not map_obj.data_uri:
            logger.warning(
                "[%s]: Skipped '%s' (%d) — no data_uri.",
                self.name,
                map_obj.name,
                map_obj.id,
            )
            return

        if not map_obj.information or not map_obj.information.farmlands_filename:
            logger.warning(
                "[%s]: Skipped '%s' (%d) — no farmlands_filename, "
                "MapsXmlHandler must run first.",
                self.name,
                map_obj.name,
                map_obj.id,
            )
            return

        info_layer = self.info_layer_repository.get_by_map_and_key(
            map_obj.id, _FARMLANDS_LAYER_KEY
        )

        if not info_layer:
            logger.warning(
                "[%s]: Skipped '%s' (%d) — no farmlands InfoLayer, "
                "InfoLayerHandler must run first.",
                self.name,
                map_obj.name,
                map_obj.id,
            )
            return

        filename = map_obj.information.farmlands_filename
        content = self._get(f"{map_obj.data_uri}/config/{filename}")
        parsed = FarmlandsXmlParser().parse(content)

        self._store(map_obj, parsed, info_layer=info_layer)

    def _store(self, map_obj: Map, parsed: FarmlandsXmlModel, **kwargs) -> None:
        """
        Store the parsed data in the database.

        :param map_obj: The parent map.
        :param parsed: The parsed FarmlandsXmlModel.
        :param kwargs: Expects 'info_layer', the farmlands InfoLayer this data belongs to.
        """
        info_layer = kwargs["info_layer"]

        for entry in parsed.farmlands:
            self.farmland_repository.upsert(
                map_id=map_obj.id,
                info_layer_id=info_layer.id,
                number=entry.farmland_number,
                price_per_ha=parsed.price_per_ha,
                price_scale=entry.price_scale,
                default=entry.default,
            )
