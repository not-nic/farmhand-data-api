"""
Map XML Parser Service Module used for parsing a map's extracted XML
files into structured metadata and persisting it onto the Map record.
"""

from datetime import datetime, timedelta
from time import perf_counter
from xml.etree.ElementTree import ParseError

from botocore.exceptions import ClientError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.handlers.xml.maps_xml_handler import MapsXmlHandler
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

    PARSEABLE_STATUSES = (IngestionStatus.EXTRACTED, IngestionStatus.FAILED)
    RETRY_COOLDOWN_MINUTES = 30

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
            MapsXmlHandler(db, aws, assets)
        ]

    def parse_map(self, map_obj: Map) -> None:
        """
        Run all registered handlers against a single map, each handler should be
        independent of each other so that a failure does not stop others
        from processing.

        :param map_obj: The map to parse.
        """
        started = perf_counter()
        errors: list[str] = []

        for handler in self.handlers:
            try:
                handler.process(map_obj)
            except ClientError as exc:
                message = f"S3 fetch failed in {handler.name}: {exc}"
                logger.error(
                    "[MapXmlParserService]: %s for '%s' (%d).", message, map_obj.name, map_obj.id
                )
                errors.append(message)
            except ParseError as exc:
                message = f"Invalid XML in {handler.name}: {exc}"
                logger.error(
                    "[MapXmlParserService]: %s for '%s' (%d).", message, map_obj.name, map_obj.id
                )
                errors.append(message)
            except ValidationError as exc:
                message = f"Validation failed in {handler.name}: {exc}"
                logger.error(
                    "[MapXmlParserService]: %s for '%s' (%d).", message, map_obj.name, map_obj.id
                )
                errors.append(message)

        self._update_ingestion_result(map_obj, errors, started)

    def parse(self) -> None:
        """
        Parse XML for every map that's ready — freshly extracted and never
        attempted, or previously failed during XML parsing and past its
        retry cooldown.
        """
        maps = self.map_service.get_maps_with_data_uri()
        pending = [m for m in maps if self._is_parseable(m)]

        if not pending:
            logger.debug("[MapXmlParserService]: No maps pending XML parsing.")
            return

        logger.info("[MapXmlParserService]: Parsing XML for %d map(s).", len(pending))

        for map_obj in pending:
            self.parse_map(map_obj)

    def _is_parseable(self, map_obj: Map) -> bool:
        """
        Check if a map object is in a parseable state, if a map is in a failed state,
        it must exceed a retry cooldown before it is reparsed.

        :param map_obj: The map to check.
        """
        if map_obj.ingestion_status == IngestionStatus.EXTRACTED:
            return True

        if map_obj.ingestion_status == IngestionStatus.FAILED:
            cooldown_elapsed = datetime.now() - timedelta(minutes=self.RETRY_COOLDOWN_MINUTES)
            return map_obj.ingestion_updated_at < cooldown_elapsed

        return False

    def _update_ingestion_result(
            self,
            map_obj: Map,
            errors: list[str],
            started: float
    ) -> None:
        """
        Mark the map as failed if any handlers report an error when parsing
        a map XML file.

        :param map_obj: The map whose ingestion status is being recorded.
        :param errors: Error messages collected from handler failures, if any.
        :param started: The perf_counter() timestamp when parsing began, used
                        to compute elapsed time for the success log message.
        """
        if errors:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.FAILED,
                ingestion_error="; ".join(errors),
            )
            logger.error(
                "[MapXmlParserService]: Marked '%s' (%d) as FAILED after %d handler error(s).",
                map_obj.name,
                map_obj.id,
                len(errors),
            )
            return

        self.map_service.update_map(
            map_obj,
            ingestion_status=IngestionStatus.PARSED,
            ingestion_error=None,
        )

        logger.info(
            "[MapXmlParserService]: Completed parsing all XML for '%s' (%d) in %.2fs.",
            map_obj.name,
            map_obj.id,
            perf_counter() - started,
        )