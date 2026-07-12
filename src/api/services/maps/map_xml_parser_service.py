"""
Map XML Parser Service Module used for parsing a map's extracted XML
files into structured metadata and persisting it onto the Map record.
"""

from xml.etree.ElementTree import ParseError

from botocore.exceptions import ClientError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.handlers.xml.mod_desc_handler import ModDescHandler
from src.api.services.assets.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_service import MapService


class MapXmlParserService:
    """
    Service class that orchestrates extracting XML data from each map XML
    configuration file determined by XmlHandlers defined in /handlers.

    Handlers should be listed in the order in which they need to run -
    for example, 'ModDesc.xml' has the location to vehicles, placeables,
    and other configuration files so should run first.
    """

    def __init__(
            self,
            db: Session,
            map_service: MapService | None = None,
            aws_service: AwsService | None = None,
            assets_service: AssetsService | None = None,
    ) -> None:
        self.map_service = map_service or MapService(db)

        aws = aws_service or AwsService()
        assets = assets_service or AssetsService(db)

        # Register handlers in the order they should run
        self.handlers: list[BaseXmlHandler] = [
            ModDescHandler(db, aws, assets),
        ]

    def parse_map(self, map_obj: Map) -> None:
        """
        Run all registered handlers against a single map, each handler should be
        independent of each other so that a failure does not stop others
        from processing.

        :param map_obj: The map to parse.
        """
        for handler in self.handlers:
            try:
                handler.process(map_obj)
            except ClientError as exc:
                logger.error(
                    "[MapXmlParserService]: S3 fetch failed in %s for '%s' (%d): %s",
                    handler.name,
                    map_obj.name,
                    map_obj.id,
                    exc,
                )
            except ParseError as exc:
                logger.error(
                    "[MapXmlParserService]: Invalid XML in %s for '%s' (%d): %s",
                    handler.name,
                    map_obj.name,
                    map_obj.id,
                    exc,
                )
            except ValidationError as exc:
                logger.error(
                    "[MapXmlParserService]: Validation failed in %s for '%s' (%d): %s",
                    handler.name,
                    map_obj.name,
                    map_obj.id,
                    exc,
                )

    def parse_all_mod_descriptions(self) -> None:
        """
        Parse all mod descriptions for each map that in S3
        that has a 'data_uri'.
        """
        maps = self.map_service.get_maps_with_data_uri()
        pending = [m for m in maps if m.mod_description is None]

        if not pending:
            logger.debug("[MapXmlParserService]: All maps already have a ModDescription.")
            return

        logger.info("[MapXmlParserService]: Parsing %d map(s).", len(pending))

        for map_obj in pending:
            self.parse_map(map_obj)
