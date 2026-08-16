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
    def get_pending_map_ids(self) -> set[int]:
        """
        Get the ids of every map with pending work for this layer.
        :return: Set of map ids awaiting processing.
        """
        pass

    @abstractmethod
    def process_map(self, map_obj: Map, parsed_i3d: I3dModel | None) -> None:
        """
        Process this layer's pending work for a single map. Implementations
        should no-op quickly if they have nothing pending for this map.

        :param map_obj: (Map) The map to process.
        :param parsed_i3d: (I3dModel) The map's already-parsed I3dModel, or None if
            it couldn't be fetched/parsed.
        """
        pass

    @staticmethod
    def _load_pixels(image_bytes: bytes) -> np.ndarray:
        """
        Load an index PNG as a pixel array, one value per pixel.

        A one byte per pixel layer is stored greyscale and loads as-is. A two
        byte per pixel layer is stored RGB, with the low byte in red and the
        high byte in green, so the two are recombined into the original value.

        :param image_bytes: (bytes) Raw bytes of the index PNG.
        :return: Pixel array with one value per pixel.
        """
        image = Image.open(BytesIO(image_bytes))

        if image.mode not in ("RGB", "RGBA"):
            return np.array(image.convert("L"))

        pixels: np.ndarray = np.array(image, dtype=np.uint16)

        low_byte: np.ndarray = pixels[:, :, 0]  # red
        high_byte: np.ndarray = pixels[:, :, 1]  # green

        # Each value was split over two bytes to store numbers above 255, so
        # the green byte counts in whole 256s and the red byte is the leftover:
        # green 1, red 44 is 1 * 256 + 44 = 300. Shifting green left by 8 bits
        # multiplies it by 256, and the two never overlap.
        return low_byte | (high_byte << 8)
