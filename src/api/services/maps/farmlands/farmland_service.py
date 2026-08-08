"""
Python module containing a service to extract farmland geometry (coordinates and size)
from a converted infoLayer_farmlands.grle / .png.
"""

import time
from io import BytesIO
from typing import Iterable

import cv2
import numpy as np
from PIL import Image

from src.api.core.db.models import Map, Farmland
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.core.schema.mods.i3d import I3dModel
from src.api.parsers.xml.i3d_parser import I3dParser
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_service import MapService

CONTOUR_EPSILON = 2.0  # pixel tolerance for polygon simplification


class FarmlandService:
    """
    Python service to generate farmlands from a converted .grle file.
    """
    FARMLANDS_LAYER_KEY = "farmlands"

    def __init__(self, db):
        self.farmland_repository = FarmlandRepository(db)
        self.info_layer_repository = InfoLayerRepository(db)
        self.map_service = MapService(db)
        self.aws_service = AwsService()

    def process_farmlands(self) -> None:
        """
        Create geometry data for every farmland that has been ingested.
        """
        pending = self.farmland_repository.get_pending_geometry()

        if not pending:
            return

        map_ids = {farmland.map_id for farmland in pending}

        for map_id in map_ids:
            info_layer = self.info_layer_repository.get_by_map_and_key(
                map_id,
                self.FARMLANDS_LAYER_KEY
            )

            if not info_layer or not info_layer.is_ingested:
                continue

            try:
                self._process_map(map_id, info_layer.asset_uri)
            except Exception as exc:
                logger.error(
                    "[FarmlandService]: Failed to process map %d: %s",
                    map_id,
                    exc,
                )

    def _process_map(self, map_id: int, farmlands_asset_uri: str) -> None:
        """
        Extract and persist geometry for every farmland on a single map.

        :param map_id: The map to process.
        :param farmlands_asset_uri: S3 URI of the converted farmlands PNG.
        """
        map_obj: Map = self.map_service.get_map_by_id(map_id)

        if not map_obj or not map_obj.information or not map_obj.information.width:
            logger.warning(
                "[FarmlandService]: Skipping map %d — no map width available.",
                map_id,
            )
            return

        unbuyable_values: set[int] = self._get_unbuyable_values(map_obj)

        if unbuyable_values is None:
            logger.warning(
                "[FarmlandService]: Skipping map %d — could not resolve the unbuyable "
                "value from its farmlands Option list.",
                map_id,
            )
            return

        image_bytes: bytes = self.aws_service.get_content_from_uri(farmlands_asset_uri)

        started_at: float = time.perf_counter()
        geometry: dict = self._extract_geometry(
            image_bytes,
            map_obj.information.width,
            unbuyable_values
        )

        farmlands: list[Farmland] = [
            f for f in self.farmland_repository.get_pending_geometry() if f.map_id == map_id
        ]

        found_count: int = 0
        for farmland in farmlands:
            farmland_geometry: int = geometry.get(farmland.number)

            if not farmland_geometry:
                self.farmland_repository.update(farmland, coordinates=[], size_ha=0)
                continue

            self.farmland_repository.update(
                farmland,
                coordinates=farmland_geometry["coordinates"],
                size_ha=farmland_geometry["size_ha"],
            )
            found_count += 1

        elapsed = time.perf_counter() - started_at
        logger.info(
            "[FarmlandService]: Map %d — %d/%d farmland(s) processed with geometry in %.2fs.",
            map_id,
            found_count,
            len(farmlands),
            elapsed,
        )

    def _get_unbuyable_values(self, map_obj: Map) -> set[int] | None:
        """
        Resolve which pixel value represents unbuyable/reserved area for
        this map. Farmland Option lists conventionally end with the
        reserved entry last (e.g. value="255" name="Not buyable"), so
        the last option's value is used.

        :param map_obj: The map to resolve the unbuyable value for.
        :return: Set of pixel values to exclude, or None if it couldn't be resolved.
        """
        if not map_obj.data_uri or not map_obj.information or not map_obj.information.map_i3d_filename:
            return None

        filename: str = map_obj.information.map_i3d_filename
        content: bytes = self.aws_service.get_content_from_uri(f"{map_obj.data_uri}/map/{filename}")
        parsed: I3dModel = I3dParser().parse(content)

        for layer in parsed.info_layers:
            if layer.layer_key == self.FARMLANDS_LAYER_KEY and layer.options:
                return {0, layer.options[-1].value}

        return None

    def rescale_farmlands(
            self,
            map_id: int,
            offset_x: float,
            offset_y: float,
            scale_x: float = 1.0,
            scale_y: float = 1.0,
    ) -> dict:
        """
        Apply a linear scale+offset transform to a map's stored farmland coordinates.

        Map field coordinates are done by the following calculation:
            scaled = (x * scale_x + offset_x, y * scale_y + offset_y).

        This is used within the /rescale data endpoint used to resize a map with manual
        effort to match its overview image if they do not already match.

        :param map_id: The map whose farmlands should be rescaled.
        :param offset_x: X offset to add after scaling.
        :param offset_y: Y offset to add after scaling.
        :param scale_x: X scale factor, applied before the offset.
        :param scale_y: Y scale factor, applied before the offset.
        :return: Summary dict with the count affected and before/after bounding boxes.
        """
        farmlands: list[Farmland] = self.farmland_repository.get_by_map_id(map_id)
        farmlands_with_geometry: list[Farmland] = [f for f in farmlands if f.coordinates]

        if not farmlands_with_geometry:
            raise ValueError(f"No farmlands with existing coordinates found for map {map_id}.")

        before_bounds: dict = self._bounding_box(farmlands_with_geometry)

        transformed_by_farmland: dict = {
            farmland.number: [
                [round(x * scale_x + offset_x), round(y * scale_y + offset_y)]
                for x, y in farmland.coordinates
            ]
            for farmland in farmlands_with_geometry
        }

        for farmland in farmlands_with_geometry:
            self.farmland_repository.update(
                farmland, coordinates=transformed_by_farmland[farmland.number]
            )

        logger.info(
            "[FarmlandService]: Rescaled %d farmland(s) on map %d (offset=%s,%s scale=%s,%s).",
            len(farmlands_with_geometry), map_id, offset_x, offset_y, scale_x, scale_y,
        )

        return {
            "map_id": map_id,
            "farmlands_affected": len(farmlands_with_geometry),
            "transform": {
                "offset_x": offset_x,
                "offset_y": offset_y,
                "scale_x": scale_x,
                "scale_y": scale_y,
            },
            "bounds_before": before_bounds,
            "bounds_after": self._bounding_box_from_coords(transformed_by_farmland.values()),
        }

    def _extract_geometry(
            self,
            image_bytes: bytes,
            map_width_meters: int,
            unbuyable_values: set[int]
    ) -> dict[int, dict]:
        """
        Extract per-farmland coordinates and size from a farmlands index PNG.

        :param image_bytes: Raw bytes of the farmlands index PNG.
        :param map_width_meters: The map's pixel width, used to scale
            pixel measurements into real-world hectares AND to normalize
            farmland coordinates into the same space.
        :param unbuyable_values: Pixel values to exclude, from _get_unbuyable_values.
        :return: {farmland_number: {"coordinates": ..., "size_ha": ...}}
        """
        pixels: np.ndarray = self._load_pixels(image_bytes)
        info_layer_width_px: int = pixels.shape[1]
        pixels_per_hectare: float = self._pixels_per_hectare(info_layer_width_px, map_width_meters)

        coordinate_scale: float = map_width_meters / info_layer_width_px

        sizes: dict = self._calculate_field_sizes(pixels, pixels_per_hectare, unbuyable_values)

        return {
            farmland_number: {
                "coordinates": self._largest_contour(pixels, farmland_number, coordinate_scale),
                "size_ha": size_ha,
            }
            for farmland_number, size_ha in sizes.items()
        }

    @staticmethod
    def _load_pixels(image_bytes: bytes) -> np.ndarray:
        """
        Load a farmlands index PNG as a greyscale pixel array.

        :param image_bytes: Raw bytes of the farmlands index PNG.
        :return: Greyscale pixel array, one value per pixel.
        """
        image = Image.open(BytesIO(image_bytes)).convert("L")
        return np.array(image)

    @staticmethod
    def _pixels_per_hectare(image_width_px: int, map_width_meters: int) -> float:
        """
        Calculate how many pixels make up one hectare, based on the
        map's real-world width relative to the info layer's resolution.

        :param image_width_px: Width of the farmlands PNG in pixels.
        :param map_width_meters: The map's pixel width in meters.
        :return: Pixels per hectare.
        """
        meters_per_pixel: float = map_width_meters / image_width_px
        return 10_000 / (meters_per_pixel ** 2)

    @staticmethod
    def _calculate_field_sizes(
            pixels: np.ndarray,
            pixels_per_hectare: float,
            unbuyable_values: set[int]
    ) -> dict[int, float]:
        """
        Calculate the area of every farmland present in the pixel array.

        :param pixels: Greyscale pixel array.
        :param pixels_per_hectare: Pixels per hectare, from _pixels_per_hectare.
        :param unbuyable_values: Pixel values to exclude, from _get_unbuyable_values.
        :return: {farmland_number: size_ha}
        """
        values, counts = np.unique(pixels, return_counts=True)

        return {
            int(value): round(count / pixels_per_hectare, 2)
            for value, count in zip(values, counts)
            if int(value) not in unbuyable_values
        }

    @staticmethod
    def _largest_contour(
            pixels: np.ndarray,
            farmland_number: int,
            coordinate_scale: float = 1.0
    ) -> list[list[int]] | None:
        """
        Find the largest polygon boundary for a single farmland. Only the largest
        contour is kept as a storage optimisation.

        Note: Farmlands split across multiple disconnected areas will lose its smaller pieces.

        :param pixels: Greyscale pixel array.
        :param farmland_number: The farmland's pixel value.
        :param coordinate_scale: Multiplier is applied to every vertex to
            convert from the farmlands PNG's own pixel space into the
            map's width/height space (see _extract_geometry). 1.0 for
            maps where the farmlands PNG already matches the map size.
        :return: List of [x, y] polygon vertices, or None if no contour was found.
        """
        mask: np.ndarray = (pixels == farmland_number).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        largest = max(contours, key=len)
        simplified = cv2.approxPolyDP(largest, CONTOUR_EPSILON, True)
        coordinates = simplified.squeeze().tolist()

        # A single-point contour squeezes down to a flat [x, y] pair
        # rather than a list of pairs — wrap it back into one.
        if coordinates and isinstance(coordinates[0], int):
            coordinates = [coordinates]

        if coordinate_scale != 1.0:
            coordinates = [
                [round(x * coordinate_scale), round(y * coordinate_scale)]
                for x, y in coordinates
            ]

        return coordinates

    @staticmethod
    def _bounding_box(farmlands: list[Farmland]) -> dict:
        """
        Compute the combined min/max x/y bounds across a list of farmlands.

        :param farmlands: Farmlands to include, each with a `coordinates` list.
        :return: {"min_x", "min_y", "max_x", "max_y"} in the same units as the input coordinates.
        """
        return FarmlandService._bounding_box_from_coords(f.coordinates for f in farmlands)

    @staticmethod
    def _bounding_box_from_coords(coordinate_lists: Iterable[list]) -> dict:
        """
        Compute the combined min/max x/y bounds across several coordinate lists.

        :param coordinate_lists: Iterable of coordinate lists, each a list of [x, y] pairs.
        :return: {"min_x", "min_y", "max_x", "max_y"}, or all None if empty.
        """
        coordinate_lists = list(coordinate_lists)
        xs = [x for coords in coordinate_lists for x, _ in coords]
        ys = [y for coords in coordinate_lists for _, y in coords]
        if not xs:
            return {"min_x": None, "min_y": None, "max_x": None, "max_y": None}
        return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}
