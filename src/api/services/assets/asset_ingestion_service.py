"""
Python module containing an asset ingestion service, to ingest non-converted .dds
assets into a web-friendly format and make them publicly accessible to the asset
bucket via pre-signed URLs.
"""
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from wand.exceptions import WandException

from src.api.constants import EntityType
from src.api.core.config import settings
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories.asset_repository import AssetRepository
from src.api.services.assets.assets_service import AssetsService
from src.api.services.maps.map_service import MapService


class AssetIngestionService:
    """
    Python service class to process image assets and put them into
    the asset bucket.
    """

    def __init__(self, db: Session):
        self.assets_service = AssetsService(db)
        self.map_service = MapService(db)
        self.asset_repository = AssetRepository(db)

    def process_map_assets(self) -> None:
        """
        Get pending map assets and convert them from a .dds into a .webp
        image that is accessible to the assets bucket.
        """
        pending = self.asset_repository.get_pending(
            entity_type=EntityType.MAP
        )[:settings.MAX_ASSET_INGESTION_BATCH]

        if not pending:
            return

        ingested: list[int] = []

        for asset in pending:
            map_obj: Map = self.map_service.get_map_by_id(asset.entity_id)
            if not map_obj or not map_obj.data_uri:
                logger.warning(
                    "[Asset-Ingestion]: Skipping map_id=%d filename='%s' — no data_uri.",
                    asset.entity_id, asset.filename,
                )
                continue

            try:
                self.assets_service.store_converted_image(
                    asset.entity_id, map_obj.data_uri, asset.filename
                )
                self.asset_repository.mark_ingested(asset)
                ingested.append(asset.entity_id)
            except ClientError as exc:
                logger.error(
                    "[Asset-Ingestion]: Failed to fetch map_id=%d filename='%s' from S3: %s",
                    asset.entity_id, asset.filename, exc,
                )
            except WandException as exc:
                logger.error(
                    "[Asset-Ingestion]: Failed to convert map_id=%d filename='%s': %s",
                    asset.entity_id, asset.filename, exc,
                )

        logger.info(
            "[Asset-Ingestion]: %d/%d asset(s) ingested. map_ids=%s",
            len(ingested), len(pending), ingested,
        )
