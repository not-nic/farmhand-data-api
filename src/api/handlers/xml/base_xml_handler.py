"""
Abstract base class for XML handlers in the farmhand pipeline.

Handlers sit between parsers and the database — they own the fetch,
parse and persist lifecycle for a single XML file type.
"""

from abc import ABC, abstractmethod

from botocore.exceptions import ClientError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.constants import AssetType, EntityType
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.services.assets.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService


class BaseXmlHandler[T: BaseModel](ABC):
    """
    Abstract base for XML handlers.

    Each subclass targets a single XML file type, implementing a process
    function to fetch from S3, delegate to the appropriate parser, and persist
    the result. _fetch is provided as a shared S3 helper.
    """

    def __init__(
        self,
        db: Session,
        aws_service: AwsService,
        assets_service: AssetsService | None = None,
    ) -> None:
        self.db = db
        self.aws_service = aws_service
        self.assets_service = assets_service

    @property
    def name(self) -> str:
        """
        Name property for the base class using a dunder method.
        :return: (str) the base class name.
        """
        return self.__class__.__name__

    @abstractmethod
    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and store data for a given XML file.
        :param map_obj: The map to process.
        """
        pass

    @abstractmethod
    def _store(self, map_obj: Map, parsed: T, **kwargs) -> None:
        """
        Store the parsed data in the database.

        :param map_obj: The parent map.
        :param parsed: The parsed Pydantic model.
        """
        pass

    def _get(self, uri: str) -> bytes:
        """
        Get raw XML bytes from an S3 URI.
        :param uri: Full S3 URI of the XML file.
        :return: Raw bytes of the XML file.
        :raises ClientError: If the S3 fetch fails.
        """
        try:
            return self.aws_service.get_content_from_uri(uri)
        except ClientError as exc:
            logger.error(
                "[%s]: Failed to fetch '%s' from S3: %s",
                self.name,
                uri,
                exc,
            )
            raise

    def _register_asset(self, map_obj: Map, filename: str, asset_type: AssetType) -> None:
        """
        Register an asset that needs to be created against a given map.
        :param map_obj: The parent map.
        :param filename: The original .dds filename from the XML.
        :param asset_type: The type of asset (icon, preview, overview, etc.).
        """
        if not self.assets_service:
            raise ValueError(f"{self.name} has no assets_service configured.")

        self.assets_service.register_asset_from_filename(
            entity_id=map_obj.id,
            entity_type=EntityType.MAP,
            filename=filename,
            asset_type=asset_type,
        )
