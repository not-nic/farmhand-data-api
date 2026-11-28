"""
A Python module containing the Map Ingestion Service, the overall
service to manage, getting new maps, ingesting them, and storing map
data.
"""

from collections.abc import Collection
from zipfile import BadZipFile

from botocore.exceptions import ClientError
from httpx2 import HTTPError
from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus, XmlHandler
from src.api.core.config import settings
from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_download_service import MapDownloadService
from src.api.services.maps.map_extraction_service import MapExtractionService
from src.api.services.maps.map_scraping_service import MapScrapingService
from src.api.services.maps.map_service import MapService
from src.api.services.maps.map_xml_parser_service import MapXmlParserService
from src.api.services.maps.recovery.map_recovery_service import MapRecoveryService


class MapIngestionService:
    """
    Python class to manage the map ingestion scrape from ModHUb,
    download the archive, extract it, parse the XML, persist
    the result, and clean up.
    """

    def __init__(
            self,
            db: Session,
            map_service: MapService | None = None,
            scraper_service: MapScrapingService | None = None,
            download_service: MapDownloadService | None = None,
            extraction_service: MapExtractionService | None = None,
            xml_parser_service: MapXmlParserService | None = None,
            aws_service: AwsService | None = None,
            recovery_service: MapRecoveryService | None = None,
            info_layer_repository: InfoLayerRepository | None = None,
            farmland_repository: FarmlandRepository | None = None,
    ):
        self.map_service = map_service or MapService(db)
        self.scraper_service = scraper_service or MapScrapingService(db)
        self.download_service = download_service or MapDownloadService()
        self.extraction_service = extraction_service or MapExtractionService(db)
        self.xml_parser_service = xml_parser_service or MapXmlParserService(db)
        self.aws_service = aws_service or AwsService()
        self.recovery_service = recovery_service or MapRecoveryService(db)
        self.info_layer_repository = info_layer_repository or InfoLayerRepository(db)
        self.farmland_repository = farmland_repository or FarmlandRepository(db)

    VALID_STAGES = (IngestionStatus.PENDING, IngestionStatus.EXTRACTED, IngestionStatus.PARSED)

    async def get_new_maps(self) -> None:
        """
        Check ModHub for new or updated maps, scrape their metadata,
        and run the full ingestion pipeline against each one.
        """
        new_map_candidates = await self.scraper_service.check_for_new_maps()

        if not new_map_candidates:
            logger.info("All scraped and downloaded maps up to date.")
            return

        scraped_count: int = 0
        for candidate in new_map_candidates:
            try:
                map_obj: Map = await self.scraper_service.scrape_map_details(
                    candidate.preview.id,
                    prefetched_detail=candidate.prefetched_detail,
                )
            except (ValueError, HTTPError) as exc:
                logger.warning(
                    "Skipping map '%s' (%d) - failed to scrape details: %s",
                    candidate.preview.name,
                    candidate.preview.id,
                    exc,
                )
                continue

            if map_obj is None:
                continue

            scraped_count += 1

        logger.info(
            "Successfully scraped '%d' maps from the ModHub.", scraped_count
        )

    def download_pending_maps(self) -> None:
        """
        Check all maps with a status of PENDING and download it from the ModHub
        and store the archive in S3.
        Called by the AP Scheduler on a set interval to keep up with mods.
        """
        if not settings.ENABLE_MAP_DOWNLOADS:
            logger.info("Map downloads disabled — skipping download_pending_maps.")
            return

        pending_maps = self.map_service.get_maps_by_status(IngestionStatus.PENDING)[:settings.MAX_MAP_DOWNLOADS]

        if not pending_maps:
            return

        logger.info("Found %d PENDING map(s) to download.", len(pending_maps))

        for map_obj in pending_maps:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.DOWNLOADING,
                ingestion_error=None,
            )
            self._download_map(map_obj)

        logger.info("All %d map(s) downloaded.", len(pending_maps))

    def reprocess_stalled_downloads(self) -> None:
        """Reset maps stalled at DOWNLOADING back to PENDING."""
        self.recovery_service.retry_stalled_downloads()

    def extract_files_from_maps(self) -> None:
        """
        Get every downloaded map, extract its files from the S3 archive,
        and re-upload the filtered and restructured contents.

        All maps being 'extracted' are tagged with the status 'EXTRACTING' so
        that they are not picked up on later runs.
        """
        downloaded_maps = self.map_service.get_maps_by_status(IngestionStatus.DOWNLOADED)

        if not downloaded_maps:
            logger.debug("No maps with status: 'DOWNLOADED'.")
            return

        logger.info("Found %d DOWNLOADED map(s) to extract.", len(downloaded_maps))

        for map_obj in downloaded_maps:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.EXTRACTING,
                ingestion_error=None,
            )
            self._extract_map(map_obj)

        logger.info("Finished extraction for %d map(s).", len(downloaded_maps))

    def parse_map_xml(self) -> None:
        """
        Parse XML files for every EXTRACTED map that's ready, or any
        previously FAILED map past its retry cooldown.
        """
        self.xml_parser_service.parse()

    def advance_parsed_maps(self) -> None:
        """Pick up every PARSED map, transfer assets, and mark it COMPLETE."""
        pass

    def reingest_map(
            self,
            map_id: int,
            stage: IngestionStatus,
            handlers: Collection[XmlHandler] | None = None,
    ) -> None:
        """
        Manually reingest a map, optionally starting from a later stage.

        :param map_id: The ModHub ID of the map to reingest.
        :param stage: Which stage to start the reingest from.
        :param handlers: If given, only re-run these XML handlers instead of every
            handler in the 'EXTRACTED' stage, and only reset the downstream
            ingestion state (info layers/farmlands) owned by a selected handler.
            Only valid when stage is 'EXTRACTED'.
        :raises ValueError: If no map with the given ID exists, from_stage isn't
            a supported starting point, or handlers is given with a stage other
            than 'EXTRACTED'.
        """
        if stage not in self.VALID_STAGES:
            raise ValueError(f"Cannot reingest from stage '{stage.value}'.")

        if handlers is not None and stage != IngestionStatus.EXTRACTED:
            raise ValueError(
                "Handlers can only be selected when reingesting from stage 'EXTRACTED'."
            )

        map_obj = self.map_service.get_map_by_id(map_id)

        if map_obj is None:
            raise ValueError(f"No map found with ID {map_id}.")

        if handlers is not None and not map_obj.data_uri:
            logger.info(
                "Skipping selective reingest for '%s' (%d) — no data_uri.",
                map_obj.name,
                map_obj.id,
            )
            return

        logger.info(
            "Starting manual reingest for '%s' (%d) from %s.",
            map_obj.name,
            map_obj.id,
            stage.value,
        )

        if stage == IngestionStatus.PENDING:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.DOWNLOADING,
                ingestion_error=None,
            )
            self._download_map(map_obj)

            map_obj = self.map_service.get_map_by_id(map_id)

            if map_obj.ingestion_status != IngestionStatus.DOWNLOADED:
                logger.error(
                    "Reingest for '%s' (%d) aborted — download did not complete.",
                    map_obj.name,
                    map_obj.id,
                )
                return

            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.EXTRACTING,
                ingestion_error=None,
            )
            self._extract_map(map_obj)

            map_obj = self.map_service.get_map_by_id(map_id)

            if map_obj.ingestion_status != IngestionStatus.EXTRACTED:
                logger.error(
                    "Reingest for '%s' (%d) aborted — extraction did not complete.",
                    map_obj.name,
                    map_obj.id,
                )
                return

        self.xml_parser_service.parse_map(map_obj, handlers)
        self._reset_downstream_ingestion(map_obj, handlers)

        logger.info("Reingest complete for '%s' (%d).", map_obj.name, map_obj.id)

    def reingest_all_maps(
            self,
            stage: IngestionStatus,
            handlers: Collection[XmlHandler] | None = None,
    ) -> None:
        """
        Reset every map to a given stage for the scheduled pipeline to
        retry, rather than reprocessing sequentially here. If handlers are
        given, there's no status to reset the maps to — a status alone
        can't express "just re-run vehicles" — so each map is reprocessed
        directly instead.

        :param stage: Which stage to reset every map to, or reprocess from.
        :param handlers: If given, only re-run these XML handlers (and their
            matching downstream reset) against every map that has a
            data_uri, processing each one immediately rather than resetting
            its status for the scheduler. Only valid when stage is 'EXTRACTED'.
        :raises ValueError: If from_stage isn't a supported starting point, or
            handlers is given with a stage other than 'EXTRACTED'.
        """
        if stage not in self.VALID_STAGES:
            raise ValueError(f"Cannot reingest from stage '{stage.value}'.")

        if handlers is not None and stage != IngestionStatus.EXTRACTED:
            raise ValueError(
                "Handlers can only be selected when reingesting from stage 'EXTRACTED'."
            )

        if handlers is not None:
            self._reingest_all_maps_with_handlers(handlers)
            return

        maps = self.map_service.get_maps()

        if not maps:
            logger.info("No maps found to reingest.")
            return

        for map_obj in maps:
            if stage == IngestionStatus.PENDING:
                self.map_service.update_map(
                    map_obj,
                    ingestion_status=stage,
                    ingestion_error=None,
                    data_uri=None,
                )
            else:
                self.map_service.update_map(
                    map_obj,
                    ingestion_status=stage,
                    ingestion_error=None,
                )
                self._reset_downstream_ingestion(map_obj)

        logger.info("Reset %d map(s) to %s.", len(maps), stage.value)

    def _reingest_all_maps_with_handlers(self, handlers: Collection[XmlHandler]) -> None:
        """
        Immediately re-run a subset of XML handlers against every map with a
        data_uri, rather than resetting a status for the scheduler to pick up.

        :param handlers: Which XML handlers to re-run (and whose matching
            downstream ingestion state to reset) for each map.
        """
        maps = self.map_service.get_maps_with_data_uri()

        if not maps:
            logger.info("No maps with a data_uri found to reingest.")
            return

        reingested_count = 0
        for map_obj in maps:
            try:
                self.xml_parser_service.parse_map(map_obj, handlers)
                self._reset_downstream_ingestion(map_obj, handlers)
                reingested_count += 1
            except Exception as exc:
                logger.error(
                    "Selective reingest failed for '%s' (%d): %s",
                    map_obj.name,
                    map_obj.id,
                    exc,
                )

        logger.info(
            "Selectively reingested %d/%d map(s) for handlers %s.",
            reingested_count,
            len(maps),
            sorted(handlers),
        )

    def _reset_downstream_ingestion(
            self,
            map_obj: Map,
            handlers: Collection[XmlHandler] | None = None,
    ) -> None:
        """
        Reset the ingestion state of anything derived from this map's
        GRLE/geometry data, so the async conversion and geometry jobs
        reprocess it against the freshly re-extracted files rather than
        skipping it as already done.

        :param map_obj: The map that was just reparsed.
        :param handlers: If given, only reset info layers when INFO_LAYERS is
            selected, and only reset farmlands when FARMLANDS is selected.
            If omitted, both are reset.
        """
        if handlers is None or XmlHandler.INFO_LAYERS in handlers:
            for info_layer in self.info_layer_repository.get_by_map_id(map_obj.id):
                self.info_layer_repository.update(info_layer, is_ingested=False, asset_uri=None)

        if handlers is None or XmlHandler.FARMLANDS in handlers:
            for farmland in self.farmland_repository.get_by_map_id(map_obj.id):
                self.farmland_repository.update(
                    farmland, area_types=None, coordinates=None, size_ha=None
                )

        logger.debug(
            "Reset downstream ingestion state for '%s' (%d).",
            map_obj.name,
            map_obj.id,
        )

    def _download_map(self, map_obj: Map) -> None:
        """
        Download a single map archive to S3 and advance its status, or
        mark it FAILED with the error if anything goes wrong.
        """
        logger.info("Downloading map '%s' (%d).", map_obj.name, map_obj.id)
        try:
            self.download_service.download_map(map_obj.id, map_obj.zip_filename)
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.DOWNLOADED,
                ingestion_error=None,
            )
        except (ClientError, HTTPError) as exc:
            logger.error("Failed to download map '%s' (%d): %s", map_obj.name, map_obj.id, exc)
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.FAILED,
                ingestion_error=str(exc),
            )

    def _extract_map(self, map_obj: Map) -> None:
        """
        Extract and restructure files for a single map and advance its status,
        or mark it FAILED with the error if anything goes wrong.
        """
        logger.info("Extracting files from map '%s' (%d).", map_obj.name, map_obj.id)
        try:
            self.extraction_service.extract_map_files(map_obj)
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.EXTRACTED,
                ingestion_error=None,
            )

            # Delete archive after files successfully extracted.
            archive_key = f"{map_obj.id}/{map_obj.zip_filename}"
            self.aws_service.delete_object(key=archive_key)

        except (MapProcessingError, BadZipFile, ClientError) as exc:
            logger.error(
                "Failed to extract map '%s' (%d): %s", map_obj.name, map_obj.id, exc
            )
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.FAILED,
                ingestion_error=str(exc),
            )
