"""
Python module containing a service to convert raw vehicle .dds store images
into .png images in the assets bucket.
"""

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from wand.exceptions import WandException

from src.api.constants import ContentType
from src.api.core.config import settings
from src.api.core.db.models import Asset
from src.api.core.logger import logger
from src.api.core.repositories import AssetRepository
from src.api.services.assets.assets_service import AssetsService
from src.api.utils import key_from_s3_uri


class VehicleAssetIngestionService:
    """
    Service to convert pending vehicle assets and put them in the assets bucket.
    """

    OUTPUT_FORMAT: str = "png"

    def __init__(self, db: Session, assets_service: AssetsService | None = None):
        self.assets_service = assets_service or AssetsService(db)
        self.asset_repository = AssetRepository(db)

    def process_pending(self) -> None:
        """
        Get a batch of pending vehicle assets, convert them from .dds into .png
        and upload them to the assets bucket.
        """
        pending: list[Asset] = self.asset_repository.get_pending_vehicle_assets(
            limit=settings.MAX_VEHICLE_ASSET_INGESTION_BATCH
        )

        if not pending:
            return

        ingested = 0

        for asset in pending:
            try:
                self.assets_service.convert_and_store(
                    source_uri=self.assets_service.ingest_bucket.build_uri(asset.filename),
                    asset_key=key_from_s3_uri(asset.asset_uri),
                    output_format=self.OUTPUT_FORMAT,
                    content_type=ContentType.PNG,
                )
                self.asset_repository.mark_ingested(asset)
                ingested += 1
            except ClientError as exc:
                logger.error(
                    "[Vehicle-Asset-Ingestion]: Failed to fetch vehicle_id=%s filename='%s' from S3: %s",
                    asset.vehicle_id, asset.filename, exc,
                )
            except WandException as exc:
                logger.error(
                    "[Vehicle-Asset-Ingestion]: Failed to convert vehicle_id=%s filename='%s': %s",
                    asset.vehicle_id, asset.filename, exc,
                )

        logger.info(
            "[Vehicle-Asset-Ingestion]: %d/%d asset(s) ingested.", ingested, len(pending)
        )
