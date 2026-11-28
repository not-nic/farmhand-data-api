"""
Map XML Parser Service Module used for parsing a map's extracted XML
files into structured metadata and persisting it onto the Map record.
"""

from collections.abc import Collection
from datetime import datetime
from time import perf_counter
from xml.etree.ElementTree import ParseError

from botocore.exceptions import ClientError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus, XmlHandler
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.handlers.xml.farmland_xml_handler import FarmlandsXmlHandler
from src.api.handlers.xml.i3d.info_layer_handler import InfoLayerHandler
from src.api.handlers.xml.maps_xml_handler import MapsXmlHandler
from src.api.handlers.xml.mod_desc_handler import ModDescHandler
from src.api.handlers.xml.vehicles_xml_handler import VehiclesXmlHandler
from src.api.services.assets.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_service import MapService
from src.api.utils import is_past_retry_cooldown


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
            VehiclesXmlHandler(db, aws, assets),
            MapsXmlHandler(db, aws, assets),
            InfoLayerHandler(db, aws),
            FarmlandsXmlHandler(db, aws),
        ]

    def parse_map(self, map_obj: Map, handlers: Collection[XmlHandler] | None = None) -> None:
        """
        Run registered handlers against a single map, each handler should be
        independent of each other so that a failure does not stop others
        from processing.

        :param map_obj: The map to parse.
        :param handlers: If given, only run the handlers whose key is in this
            collection, in their registered order, and leave the map's
            ingestion_status untouched — intended for a targeted, selective
            re-run rather than a full parse. If omitted, every registered
            handler runs and the ingestion_status is updated as normal.
        """
        started = perf_counter()
        errors: list[str] = []

        to_run = self.handlers if handlers is None else [
            handler for handler in self.handlers if handler.key in handlers
        ]

        for handler in to_run:
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

        if handlers is None:
            self._update_ingestion_result(map_obj, errors)
        elif errors:
            logger.warning(
                "[MapXmlParserService]: Selective reparse of %s for '%s' (%d) hit %d error(s): %s",
                sorted(handlers),
                map_obj.name,
                map_obj.id,
                len(errors),
                "; ".join(errors),
            )

        logger.info(
            "[MapXmlParserService]: Completed parsing %s for '%s' (%d) in %.2fs.",
            "all XML" if handlers is None else f"{sorted(handlers)} XML",
            map_obj.name,
            map_obj.id,
            perf_counter() - started,
        )

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

        if map_obj.ingestion_status != IngestionStatus.FAILED:
            return False

        return is_past_retry_cooldown(map_obj, self.RETRY_COOLDOWN_MINUTES)

    def _update_ingestion_result(
            self,
            map_obj: Map,
            errors: list[str],
    ) -> None:
        """
        Mark the map as failed if any handlers report an error when parsing
        a map XML file.

        :param map_obj: The map whose ingestion status is being recorded.
        :param errors: Error messages collected from handler failures, if any.
        """
        now: datetime = datetime.now()

        if errors:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.FAILED,
                ingestion_error="; ".join(errors),
                ingestion_updated_at=now
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
            ingestion_updated_at=now
        )
