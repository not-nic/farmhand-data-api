"""
Python module containing an abstract base class for map layer builders.
"""

from abc import ABC, abstractmethod
from io import BytesIO

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from src.api.core.db.models import Map
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.core.schema.mods.i3d import I3dModel
from src.api.parsers.xml.i3d_parser import I3dParser
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_service import MapService

FARMLANDS_LAYER_KEY = "farmlands"
ENVIRONMENT_LAYER_KEY = "environment"


class BaseMapLayerBuilder(ABC):
    """
    Base class for a single map layer builder, requires each implementation
    to implement process_pending() to handle each layer within amap.
    """

    def __init__(self, db: Session) -> None:
        self.info_layer_repository = InfoLayerRepository(db)
        self.map_service = MapService(db)
        self.aws_service = AwsService()

    @property
    def name(self) -> str:
        """
        A name property for each subclass.
        :return: (str) the concrete builder class name.
        """
        return self.__class__.__name__

    @abstractmethod
    def process_pending(self) -> None:
        """
        Process every map with pending work for this layer.
        """
        pass

    def _parse_i3d(self, map_obj: Map) -> I3dModel | None:
        """
        Fetch and parse a map's map.i3d file.

        :param map_obj: The map to fetch map.i3d for.
        :return: Parsed I3dModel, or None if it couldn't be fetched.
        :raises ClientError: If the S3 fetch fails.
        :raises ParseError: If the content is not valid XML.
        """
        if not map_obj.data_uri or not map_obj.information or not map_obj.information.map_i3d_filename:
            return None

        filename: str = map_obj.information.map_i3d_filename
        content: bytes = self.aws_service.get_content_from_uri(f"{map_obj.data_uri}/map/{filename}")
        return I3dParser().parse(content)

    @staticmethod
    def _load_pixels(image_bytes: bytes) -> np.ndarray:
        """
        Load an index PNG as a greyscale pixel array.

        :param image_bytes: Raw bytes of the index PNG.
        :return: Greyscale pixel array, one value per pixel.
        :raises UnidentifiedImageError: If the bytes aren't a valid image.
        """
        image = Image.open(BytesIO(image_bytes)).convert("L")
        return np.array(image)
