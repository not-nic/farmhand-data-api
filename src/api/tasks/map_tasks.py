"""
Tasks for ingesting maps into the farmhand data-api in the background.
"""

from src.api.core.db.db_setup import db_session
from src.api.core.logger import logger
from src.api.services.maps.map_ingestion_service import MapIngestionService
from src.api.services.maps.map_service import MapService


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
    Background task to pick up all PENDING maps and download them to S3.
    Maps are claimed as DOWNLOADING before the transfer starts, so
    later ticks cannot attempt the same download concurrently.
    """
    with db_session() as db:
        logger.info("[MAP TASKS]: Checking for PENDING maps to download.")
        await MapIngestionService(db=db).download_pending_maps()
