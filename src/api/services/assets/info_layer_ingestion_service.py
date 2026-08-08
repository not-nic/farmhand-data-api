"""
Python module containing an info layer ingestion service, to convert
raw .grle info layer files into .png images.
"""

from botocore.exceptions import ClientError

from src.api.core.db.models import Map
from src.api.core.db.models.maps import InfoLayer
from src.api.core.logger import logger
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.services.aws.aws_service import AwsService
from src.api.services.image_converter_service import ImageConverterService
from src.api.services.maps.map_service import MapService
from src.api.utils import key_from_s3_uri


class InfoLayerIngestionService:
    """
    Python service class to convert pending info layer .grle files into
    .png images, replacing them in the ingest bucket.
    """

    def __init__(self, db):
        self.info_layer_repository = InfoLayerRepository(db)
        self.map_service = MapService(db)
        self.aws_service = AwsService()
        self.image_converter = ImageConverterService()

    def process_info_layers(self) -> None:
        """
        Convert every pending info layer's .grle into a .png, replacing it in the ingest bucket.
        """
        pending = self.info_layer_repository.get_pending()

        if not pending:
            return

        ingested: list[int] = []

        for layer in pending:
            try:
                self._convert_layer(layer)
                ingested.append(layer.map_id)
            except ClientError as exc:
                logger.error(
                    "[InfoLayer-Ingestion]: Failed to fetch '%s' for map %d: %s",
                    layer.grle_filename,
                    layer.map_id,
                    exc,
                )

        logger.info(
            "[InfoLayer-Ingestion]: %d/%d info layer(s) converted. map_ids=%s",
            len(ingested),
            len(pending),
            ingested
        )

    def _convert_layer(self, layer: InfoLayer) -> None:
        """
        Download a single info layer's .grle, convert it to .png, and
        replace the result back into the ingest bucket.

        :param layer: The InfoLayer to convert.
        """
        map_obj: Map = self.map_service.get_map_by_id(layer.map_id)

        if not map_obj or not map_obj.data_uri:
            logger.warning(
                "[InfoLayerIngestion]: Skipping '%s' — map %d has no data_uri.",
                layer.grle_filename,
                layer.map_id,
            )
            return

        grle_key = key_from_s3_uri(f"{map_obj.data_uri}/data/{layer.grle_filename}")
        png_key = grle_key.rsplit(".", 1)[0] + ".png"

        grle_bytes = self.aws_service.get_content_from_uri(self.aws_service.build_uri(grle_key))
        png_bytes = self.image_converter.from_grle(grle_bytes)

        self.aws_service.put_object(key=png_key, body=png_bytes, content_type="image/png")

        self.info_layer_repository.update(
            layer,
            asset_uri=self.aws_service.build_uri(png_key),
            is_ingested=True,
        )

        try:
            self.aws_service.delete_object(key=grle_key)
        except ClientError as exc:
            logger.warning(
                "[InfoLayerIngestion]: Converted '%s' but failed to delete source: %s",
                layer.grle_filename,
                exc,
            )
