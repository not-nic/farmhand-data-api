"""
Python module containing the MapRecoveryService, responsible for detecting
and resetting maps stuck in in-progress ingestion states back to a retryable
status so the pipeline can continue.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.config import settings
from src.api.core.logger import logger
from src.api.services.maps.map_service import MapService


class MapRecoveryService:
    """
    Detects maps stuck in in-progress ingestion states and resets them
    back to their preceding status so the pipeline pollers can retry them.

    Each stage has its own method, so thresholds and logging can be tuned
    independently as the pipeline grows.
    """

    def __init__(self, db: Session, map_service: MapService | None = None):
        self.map_service = map_service or MapService(db)

    async def retry_stalled_downloads(self) -> None:
        """
        Reset maps stuck in the DOWNLOADING ingestion status back to
        pending so that the next cycle downloads them.
        """
        threshold: datetime = datetime.now(UTC) - timedelta(
            minutes=settings.STALLED_DOWNLOAD_THRESHOLD_MINUTES
        )

        stalled_maps = self.map_service.get_stalled_maps(
            status=IngestionStatus.DOWNLOADING,
            stalled_before=threshold,
        )

        if not stalled_maps:
            return

        logger.info(
            "Found %d map(s) stalled at DOWNLOADING for over %d minutes — resetting to PENDING.",
            len(stalled_maps),
            settings.STALLED_DOWNLOAD_THRESHOLD_MINUTES,
        )

        for map_obj in stalled_maps:
            logger.info(
                "Resetting stalled map '%s' (%d) — stuck since %s.",
                map_obj.name,
                map_obj.id,
                map_obj.ingestion_updated_at,
            )
            self.map_service.update_map(
                map_obj,
                ingestion_status=IngestionStatus.PENDING,
                ingestion_error=f"Reset after stalling at DOWNLOADING since {map_obj.ingestion_updated_at}.",
            )
