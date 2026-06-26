"""
Tasks for ingesting maps into the farmhand data-api in the background.
"""

from src.api.core.db.db_setup import db_session
from src.api.core.logger import logger
from src.api.services.maps.map_ingestion_service import MapIngestionService


async def get_new_maps() -> None:
    """
    Background task to get new maps from the Farming Simulator ModHub,
    and scrape their metadata. Leaves each map at PENDING for the
    download poller to pick up.
    """
    with db_session() as db:
        logger.info(
            "[MAP TASKS]: Starting background task to retrieve "
            "new maps from the ModHub."
        )
        await MapIngestionService(db=db).get_new_maps()


async def download_pending_maps() -> None:
    """
    Background task to select PENDING maps and download them from the ModHub
    and store them in S3.
    """
    with db_session() as db:
        logger.info("[MAP TASKS]: Checking for PENDING maps to download.")
        await MapIngestionService(db=db).download_pending_maps()


def extract_files_from_maps() -> None:
    """
    Background task to select DOWNLOADED maps, extract and filter their
    files from the S3 archive, and re-upload the restructured contents.
    The source archive is deleted from S3 on successful extraction.
    """
    with db_session() as db:
        logger.info("[MAP TASKS]: Checking for DOWNLOADED maps to extract.")
        MapIngestionService(db=db).extract_files_from_maps()
