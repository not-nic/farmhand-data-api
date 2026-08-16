"""
Python module containing an AssetsService for creating methods to
make map assets accessible to the UI.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType, ContentType, EntityType
from src.api.core.config import settings
from src.api.core.db.models.assets import Asset
from src.api.core.logger import logger
from src.api.core.repositories.asset_repository import AssetRepository
from src.api.services.aws.aws_service import AwsService
from src.api.services.image_converter_service import ImageConverterService
from src.api.utils import key_from_s3_uri


class AssetsService:
    """
    Assets service for constructing asset URIs, registering assets,
    and other helpful tools to make assets available to the API.
    Image conversion itself is delegated to ImageConverterService.
    """

    OUTPUT_CONTENT_TYPE: ContentType = ContentType.WEBP
    OUTPUT_FORMAT: str = OUTPUT_CONTENT_TYPE.name.lower()

    def __init__(self, db: Session):
        self.db = db
        self.asset_repository = AssetRepository(db)
        self.image_converter = ImageConverterService()
        self.ingest_bucket = AwsService()
        self.assets_bucket = AwsService(bucket_name=settings.AWS_S3_ASSETS_BUCKET_NAME)

        # A bit of a workaround to ensure that the pre-signed URL generation includes
        # the public URL i.e. minio.farmhand.uk or localhost instead of the internal
        # docker network e.g. https://minio
        self.public_url_signer = AwsService(
            bucket_name=settings.AWS_S3_ASSETS_BUCKET_NAME,
            endpoint_url=settings.MINIO_PUBLIC_ENDPOINT_URL,
        )

    def register_asset_from_filename(
            self,
            entity_id: int,
            entity_type: EntityType,
            filename: str,
            asset_type: AssetType,
    ) -> Asset:
        """
        Convert a raw .dds filename to its target output format, and build
        its S3 URI and register an asset for ingestion.
        :param entity_id: The ID of the owning entity.
        :param entity_type: The type of entity (map, vehicle, etc.).
        :param filename: The original .dds filename from the XML.
        :param asset_type: The type of asset (icon, preview, overview, etc.).
        :return: The created or updated Asset.
        """
        converted_filename = self.image_converter.convert_filename(filename, self.OUTPUT_FORMAT)
        asset_uri = self.build_asset_uri(entity_id, converted_filename)

        return self.register_asset(
            entity_id=entity_id,
            entity_type=entity_type,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
        )

    def ingest_asset(
            self,
            entity_id: int,
            data_uri: str,
            entity_type: EntityType,
            filename: str,
            asset_type: AssetType,
            force: bool = False,
    ) -> Asset:
        """
        Ingest an asset is stored and registered, converting only when
        necessary.

        :param entity_id: The ID of the owning entity.
        :param data_uri: Base 'ingest' URI containing the raw assets.
        :param entity_type: The type of entity (map, vehicle, etc.).
        :param filename: The original .dds filename from the XML.
        :param asset_type: The type of asset (icon, overview, etc.).
        :param force: Re-convert and re-upload even if already registered.
        :return: The created or updated Asset.
        """
        converted_filename: str = self.image_converter.convert_filename(filename, self.OUTPUT_FORMAT)
        asset_uri: str = self.build_asset_uri(
            entity_id,
            converted_filename,
        )

        existing_assets: list[Asset] = self.asset_repository.get_by_entity(
            entity_type=entity_type,
            entity_id=entity_id,
        )

        existing: Asset | None = next(
            (asset for asset in existing_assets if asset.asset_type == asset_type),
            None,
        )

        if force or existing is None or existing.asset_uri != asset_uri:
            self.store_converted_image(
                entity_id,
                data_uri,
                filename,
            )

        return self.register_asset(
            entity_id=entity_id,
            entity_type=entity_type,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
        )

    def store_converted_image(
            self,
            entity_id: int,
            data_uri: str,
            filename: str,
    ) -> str:
        """
        Get a given raw .dds from the 'ingest' bucket, convert it, and upload
        it to the assets bucket.

        :param entity_id: The ID of the owning entity.
        :param data_uri: Base 'ingest' URI containing the raw assets.
        :param filename: The original .dds filename from the XML.
        :return: Full S3 URI of the stored (original size) asset.
        """
        converted_filename: str = self.image_converter.convert_filename(filename, self.OUTPUT_FORMAT)
        asset_key: str = self.build_asset_key(entity_id, converted_filename)

        dds_image_data: bytes = self.ingest_bucket.get_content_from_uri(
            uri=f"{data_uri}/assets/{filename}"
        )
        converted_image_data: bytes = self.image_converter.convert_image(
            dds_image_data, self.OUTPUT_FORMAT
        )

        self.assets_bucket.put_object(
            key=asset_key,
            body=converted_image_data,
            content_type=self.OUTPUT_CONTENT_TYPE.value,
        )

        logger.debug("[Assets-Service]: Stored '%s' -> '%s'.", filename, asset_key)

        return self.build_asset_uri(entity_id, converted_filename)

    def register_asset(
            self,
            entity_id: int,
            entity_type: EntityType,
            asset_type: AssetType,
            filename: str,
            asset_uri: str,
    ) -> Asset:
        """
        Upsert the Asset record for an image that already exists in S3.

        :param entity_id: The ID of the owning entity.
        :param entity_type: The type of entity (map, vehicle, etc.).
        :param asset_type: The type of asset (icon, overview, etc.).
        :param filename: The original .dds filename from the XML.
        :param asset_uri: Full S3 URI of the stored asset.
        :return: The created or updated Asset.
        """
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

    def resolve_uri(self, uri: str, expiration_time: int) -> str:
        """
        Resolve an S3 URI to a client-facing pre-signed URL.

        :param uri: (str) S3 URI e.g. 's3://farmhand-assets/123/assets/icon.webp'.
        :param expiration_time: (int) The time in seconds for the pre-signed URL to expire.
        :return: (str) Pre-signed URL resolvable by the client.
        """
        logger.debug("[Assets Service]: Resolving URI '%s'.", uri)
        return self.public_url_signer.generate_pre_signed_url(
            key_from_s3_uri(uri),
            "get_object",
            expiration_time
        )

    @staticmethod
    def build_asset_key(entity_id: int, filename: str) -> str:
        """
        Construct the S3 key (no bucket/scheme) for an asset in the assets bucket.

        :param entity_id: The owning entity's ID.
        :param filename: The asset filename (should already be converted).
        :return: S3 key, e.g. '123/assets/icon.webp'.
        """
        return f"{entity_id}/assets/{filename}"

    def build_asset_uri(self, entity_id: int, filename: str) -> str:
        """
        Construct the S3 URI for an asset in the assets bucket.

        :param entity_id: The owning entity's ID.
        :param filename: The asset filename (should already be converted).
        :return: Full S3 URI for the asset.
        """
        return self.assets_bucket.build_uri(self.build_asset_key(entity_id, filename))
