"""
Map Ingestion Service Module — the single place that knows the order
of operations for taking a map from "discovered on ModHub" to "fully
parsed and stored", and for re-running that pipeline against maps
already in the database.

This replaces the orchestration that used to be split between
MapService.get_new_maps / _process_map_download and
MapParsingService.extract_files_from_all_maps.
"""
import time

from httpx import HTTPError
from sqlalchemy.orm import Session

from src.api.core.config import settings
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.services.aws_service import AwsService
from src.api.services.maps.map_download_service import MapDownloadService
from src.api.services.maps.map_extraction_service import MapExtractionService
from src.api.services.maps.map_scraping_service import MapScrapingService
from src.api.services.maps.map_service import MapService
from src.api.services.maps.map_xml_parser_service import MapXmlParserService


class MapIngestionService:
    """
    Orchestrates the full map lifecycle: discover on ModHub, scrape
    metadata, download the archive, extract it, parse the XML, persist
    the result, and clean up the source archive.
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
    ):
        self.map_service = map_service or MapService(db)
        self.scraper_service = scraper_service or MapScrapingService(db)
        self.download_service = download_service or MapDownloadService()
        self.extraction_service = extraction_service or MapExtractionService(db)
        self.xml_parser_service = xml_parser_service or MapXmlParserService(db)
        self.aws_service = aws_service or AwsService()

    async def get_new_maps(self) -> None:
        """
        Check ModHub for new or updated maps, scrape their metadata,
        and run the full ingestion pipeline against each one.
        """
        new_map_candidates = await self.scraper_service.check_for_new_maps()

        if not new_map_candidates:
            logger.info("All scraped and downloaded maps up to date.")
            return

        processed_count: int = 0
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

            await self.ingest_map(map_obj)
            processed_count += 1

        logger.info(
            "Successfully scraped and downloaded '%d' maps from the ModHub.", processed_count
        )

    async def ingest_map(self, map_obj: Map) -> None:
        """
        Run the download -> extract -> parse -> cleanup pipeline for a
        single map if downloads are enabled.
        :param map_obj: The map object to download and process.
        """
        if not settings.ENABLE_MAP_DOWNLOADS:
            logger.info(
                "Map downloads disabled — skipping download and extraction for '%s' (%d).",
                map_obj.name,
                map_obj.id,
            )
            return

        # Download and extract files from a map.
        await self.download_service.download_map(map_obj.id, map_obj.zip_filename)
        extraction_result = self.extraction_service.extract_map_files(map_obj)

        # Attempt to parse the required maps XML files.
        self.xml_parser_service.parse_and_update()

        # TODO: add a delete_object(key: str) method to AwsService.
        self.aws_service.delete_object(key=extraction_result.object_key)

    async def reprocess_all_maps(self) -> None:
        """
        (temp) Process all maps stored in S3, extract files, and create a 'map' object.
        """
        start_time = time.monotonic()
        maps = self.map_service.get_maps()
        logger.info("Starting file extraction process for %d maps.", len(maps))

        for map_obj in maps:
            logger.info("Extracting files from map: '%s' (%d)", map_obj.name, map_obj.id)
            self.extraction_service.extract_map_files(map_obj)
            self.xml_parser_service.parse_and_update()

        elapsed_time = time.monotonic() - start_time
        logger.debug("Extracted data from %d maps in %.2f seconds.", len(maps), elapsed_time)
