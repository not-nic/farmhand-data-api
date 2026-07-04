"""
Python module containing an AssetsService for creating methods to
make map assets accessible to the UI.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType, EntityType
from src.api.core.config import settings
from src.api.core.db.models.assets import Asset
from src.api.core.logger import logger
from src.api.core.repositories.asset_repository import AssetRepository
from src.api.services.aws.public_aws_service import PublicAwsService


class AssetsService:
    """
    Assets service for constructing asset URIs, image conversion,
    and other helpful tools to make assets available to the API.
    """
    def __init__(self, db: Session):
        self.db = db
        self.asset_repository = AssetRepository(db)
        self.public_aws_service = PublicAwsService()

    @staticmethod
    def convert_filename(filename: str) -> str:
        """
        Convert a .dds filename to its .png equivalent.
        Reflects the conversion that happens when assets are processed.

        e.g. 'icon_FS25_Le_Mechet.dds' -> 'icon_FS25_Le_Mechet.png'

        :param filename: The original filename from the XML.
        :return: Filename with .png extension.
        """
        stem = filename.rsplit(".", 1)[0]
        return f"{stem}.png"

    @staticmethod
    def build_asset_uri(entity_id: int, filename: str) -> str:
        """
        Construct the S3 URI for an asset in the assets bucket.

        :param entity_id: The owning entity's ID.
        :param filename: The asset filename (should already be .png).
        :return: Full S3 URI for the asset.
        """
        return (
            f"s3://{settings.AWS_S3_ASSETS_BUCKET_NAME}"
            f"/{entity_id}/assets/{filename}"
        )

    def create_asset(
            self,
            entity_id: int,
            entity_type: EntityType,
            filename: str,
            asset_type: AssetType,
    ) -> Asset:
        """
        Convert a .dds filename, construct its S3 URI, and upsert an
        Asset record via the repository.

        :param entity_id: The ID of the owning entity.
        :param entity_type: The type of entity (map, vehicle etc.).
        :param filename: The original .dds filename from the XML.
        :param asset_type: The type of asset (icon, overview etc.).
        :return: The created or updated Asset.
        """
        png_filename = self.convert_filename(filename)
        asset_uri = self.build_asset_uri(entity_id, png_filename)

        asset = self.asset_repository.upsert(
            entity_type=entity_type,
            entity_id=entity_id,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
        )

        logger.debug(
            "[Assets-Service]: Upserted %s asset for %s %d — '%s' -> '%s'.",
            asset_type.value,
            entity_type.value,
            entity_id,
            filename,
            asset_uri,
        )

        return asset

    def resolve_uri(self, uri: str) -> str:
        """
        Resolve an S3 URI to a client-facing pre-signed URL.

        :param uri: S3 URI e.g. 's3://farmhand-assets/123/assets/icon.png'.
        :return: Pre-signed URL resolvable by the client.
        """
        logger.info("[Assets Service]: Resolving URI '%s'.", uri)
        return self.public_aws_service.generate_presigned_url_from_uri(uri)
