"""
A Python module containing the Map Ingestion Service, the overall
service to manage, getting new maps, ingesting them, and storing map
data.
"""
import asyncio
import time

from botocore.exceptions import ClientError
from httpx2 import HTTPError
from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
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
            "Successfully scraped and downloaded '%d' maps from the ModHub.", scraped_count
        )

    async def download_pending_maps(self) -> None:
        """
        Pick up every PENDING map and download it to S3.
        Called by the scheduler on a short interval; each map is claimed
        individually, so a single failure never blocks the rest of the batch.
        """
        if not settings.ENABLE_MAP_DOWNLOADS:
            logger.info("Map downloads disabled — skipping advance_pending_maps.")
            return

        pending_maps = self.map_service.get_maps_by_status(IngestionStatus.PENDING)[:10]

        if not pending_maps:
            return

        logger.info("Found %d PENDING map(s) to download.", len(pending_maps))

        for map_obj in pending_maps:
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.DOWNLOADING,
                ingestion_error=None,
            )

        await asyncio.gather(*[self._download_map(map_obj) for map_obj in pending_maps])

    async def _download_map(self, map_obj: Map) -> None:
        """
        Download a single map archive to S3 and advance its status, or
        mark it FAILED with the error if anything goes wrong.
        """
        logger.info("Downloading map '%s' (%d).", map_obj.name, map_obj.id)
        try:
            await self.download_service.download_map(map_obj.id, map_obj.zip_filename)
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.DOWNLOADED,
                ingestion_error=None,
            )
            logger.info("Map '%s' (%d) downloaded successfully.", map_obj.name, map_obj.id)
        except (ClientError, HTTPError) as exc:
            logger.error("Failed to download map '%s' (%d): %s", map_obj.name, map_obj.id, exc)
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.FAILED,
                ingestion_error=str(exc),
            )

    def advance_downloaded_maps(self) -> None:
        """Pick up every DOWNLOADED map and extract its files from S3."""
        pass

    def advance_extracted_maps(self) -> None:
        """Pick up every EXTRACTED map and parse its XML files."""
        pass

    def advance_parsed_maps(self) -> None:
        """Pick up every PARSED map, transfer assets, and mark it COMPLETE."""
        pass

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
