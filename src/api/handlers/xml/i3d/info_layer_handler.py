"""
Python module containing a handler for a map's .i3d file.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.core.schema.mods.i3d import I3dModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.i3d_parser import I3dParser
from src.api.services.aws.aws_service import AwsService


class InfoLayerHandler(BaseXmlHandler[I3dModel]):
    """
    Processes a map's .i3d file for its InfoLayer entries.
    """

    def __init__(
        self,
        db: Session,
        aws_service: AwsService,
    ) -> None:
        super().__init__(db, aws_service)
        self.info_layer_repository = InfoLayerRepository(db)

    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and store info layers from a map's .i3d file.

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

        if not map_obj.information or not map_obj.information.map_i3d_filename:
            logger.warning(
                "[%s]: Skipped '%s' (%d) — no map_i3d_filename, "
                "MapsXmlHandler must run first.",
                self.name,
                map_obj.name,
                map_obj.id,
            )
            return

        i3d_filename = map_obj.information.map_i3d_filename
        content = self._get(f"{map_obj.data_uri}/map/{i3d_filename}")
        parsed: I3dModel = I3dParser().parse(content)

        self._store(map_obj, parsed)

    def _store(self, map_obj: Map, parsed: I3dModel, **kwargs) -> None:
        """
        Store the parsed data in the database.

        :param map_obj: The parent map.
        :param parsed: The parsed I3dModel.
        """
        for layer in parsed.info_layers:
            self.info_layer_repository.upsert(
                map_id=map_obj.id,
                layer_key=layer.layer_key,
                i3d_file_id=layer.i3d_file_id,
                grle_filename=layer.grle_filename,
            )
