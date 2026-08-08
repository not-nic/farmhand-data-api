"""
Python module containing a handler for Farming Simulator maps.xml files.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories.map_information_repository import MapInformationRepository
from src.api.core.schema.maps.maps_xml import MapsXmlModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.maps_xml_parser import MapsXmlParser
from src.api.services.assets.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService


class MapsXmlHandler(BaseXmlHandler[MapsXmlModel]):
    """
    Handler class used for processing, persisting a farming simulator mod map 'maps.xml'
    file, and creating the overview.dds map asset.
    """

    def __init__(
            self,
            db: Session,
            aws_service: AwsService,
            assets_service: AssetsService,
    ) -> None:
        super().__init__(db, aws_service, assets_service)
        self.map_information_repository = MapInformationRepository(db)

    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and persist a maps.xml for the given map.
        :param map_obj: The map to process.
        """
        if not map_obj.data_uri:
            logger.warning(
                "[MapsXml-Handler]: Skipped '%s' (%d) — no data_uri.",
                map_obj.name,
                map_obj.id,
            )
            return

        if not map_obj.mod_description or not map_obj.mod_description.config_filename:
            logger.warning(
                "[MapsXml-Handler]: Skipped '%s' (%d) — no config_filename, "
                "ModDescHandler must run first.",
                map_obj.name,
                map_obj.id,
            )
            return

        config_filename = map_obj.mod_description.config_filename
        content = self._get(f"{map_obj.data_uri}/config/{config_filename}")
        parsed: MapsXmlModel = MapsXmlParser().parse(content)
        self._store(map_obj, parsed)

    def _store(self, map_obj: Map, parsed: MapsXmlModel, **kwargs) -> None:
        """
        Persist all data extracted from a maps.xml file.

        :param map_obj: The parent map.
        :param parsed: The parsed MapsXmlModel.
        """
        self.map_information_repository.upsert(
            map_id=map_obj.id,
            width=parsed.width,
            height=parsed.height,
            map_i3d_filename=parsed.map_i3d_filename,
            farmlands_filename=parsed.farmlands_filename,
            fields_filename=parsed.fields_filename,
            fill_types_filename=parsed.fill_types_filename,
        )

        if parsed.overview_filename:
            self._register_asset(map_obj, parsed.overview_filename, AssetType.OVERVIEW)


