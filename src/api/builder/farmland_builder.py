"""
Python module containing a builder to extract farmland geometry
(coordinates and size) from a converted infoLayer_farmlands.grle / .png.
"""

import time
from typing import Iterable

import cv2
import numpy as np
from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.db.models import Farmland, InfoLayer, Map
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.builder.base_layer_builder import (
    BaseMapLayerBuilder,
    FARMLANDS_LAYER_KEY,
)

CONTOUR_EPSILON = 2.0  # pixel tolerance for polygon simplification


class FarmlandBuilder(BaseMapLayerBuilder):
    """
    Builds farmland coordinates and size from a converted .grle file.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.farmland_repository = FarmlandRepository(db)

    def process_pending(self) -> None:
        """
        Create geometry data for every farmland that has been ingested.
        """
        pending: list[Farmland] = self.farmland_repository.get_pending_geometry()

        if not pending:
            return

        map_ids: set[int] = {farmland.map_id for farmland in pending}

        for map_id in map_ids:
            farmlands_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
                map_id, FARMLANDS_LAYER_KEY
            )

            if not farmlands_layer or not farmlands_layer.is_ingested:
                continue

            try:
                self._process_map(map_id, farmlands_layer.asset_uri)
            except Exception as exc:
                logger.error(
                    "[%s]: Failed to process map %d: %s",
                    self.name,
                    map_id,
                    exc,
                )

    def _process_map(self, map_id: int, farmlands_asset_uri: str) -> None:
        """
        Extract and persist geometry for every farmland on a single map.

        :param map_id: The map to process.
        :param farmlands_asset_uri: S3 URI of the converted farmlands PNG.
        :raises ClientError: If an S3 fetch fails.
        :raises ParseError: If map.i3d is not valid XML.
        :raises UnidentifiedImageError: If the farmlands PNG is unreadable.
        """
        map_obj: Map | None = self.map_service.get_map_by_id(map_id)

        if not map_obj or not map_obj.information or not map_obj.information.width:
            logger.warning(
                "[%s]: Skipping map %d — no map width available.",
                self.name,
                map_id,
            )
            return

        if map_obj.ingestion_status == IngestionStatus.FAILED:
            logger.debug(
                "[%s]: Skipping map %d — ingestion status is FAILED.",
                self.name,
                map_id,
            )
            return

        parsed_i3d = self._parse_i3d(map_obj)

        if parsed_i3d is None:
            logger.warning(
                "[%s]: Skipping map %d — could not fetch or parse map.i3d.",
                self.name,
                map_id,
            )
            return

        unbuyable_values: set[int] | None = self._get_unbuyable_values(parsed_i3d)

        if unbuyable_values is None:
            logger.warning(
                "[%s]: Skipping map %d — could not resolve the unbuyable "
                "value from its farmlands Option list.",
                self.name,
                map_id,
            )
            return

        image_bytes: bytes = self.aws_service.get_content_from_uri(farmlands_asset_uri)
        pixels: np.ndarray = self._load_pixels(image_bytes)

        started_at: float = time.perf_counter()
        geometry: dict[int, dict] = self._extract_geometry(
            pixels, map_obj.information.width, unbuyable_values
        )

        farmlands: list[Farmland] = [
            f for f in self.farmland_repository.get_pending_geometry() if f.map_id == map_id
        ]

        found_count: int = 0
        for farmland in farmlands:
            farmland_geometry: dict | None = geometry.get(farmland.number)

            if not farmland_geometry:
                self.farmland_repository.update(farmland, coordinates=[], size_ha=0)
                continue

            self.farmland_repository.update(
                farmland,
                coordinates=farmland_geometry["coordinates"],
                size_ha=farmland_geometry["size_ha"],
            )
            found_count += 1

        elapsed: float = time.perf_counter() - started_at
        logger.info(
            "[%s]: Map %d — %d/%d farmland(s) processed with geometry in %.2fs.",
            self.name,
            map_id,
            found_count,
            len(farmlands),
            elapsed,
        )

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
        :raises ValueError: If the map has no farmlands with existing coordinates.
        """
        farmlands: list[Farmland] = self.farmland_repository.get_by_map_id(map_id)
        farmlands_with_geometry: list[Farmland] = [f for f in farmlands if f.coordinates]

        if not farmlands_with_geometry:
            raise ValueError(f"No farmlands with existing coordinates found for map {map_id}.")

        before_bounds: dict = self._bounding_box(farmlands_with_geometry)

        transformed_by_farmland: dict[int, list[list[int]]] = {
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
            "[%s]: Rescaled %d farmland(s) on map %d (offset=%s,%s scale=%s,%s).",
            self.name,
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
            pixels: np.ndarray,
            map_width_meters: int,
            unbuyable_values: set[int],
    ) -> dict[int, dict]:
        """
        Extract per-farmland coordinates and size from a farmlands pixel array.

        :param pixels: Greyscale farmlands pixel array.
        :param map_width_meters: The map's pixel width, used to scale pixel measurements
            into real-world hectares AND to normalise farmland coordinates into the same space.
        :param unbuyable_values: Pixel values to exclude, from _get_unbuyable_values.
        :return: {farmland_number: {"coordinates": ..., "size_ha": ...}}
        """
        info_layer_width_px: int = pixels.shape[1]
        pixels_per_hectare: float = self._pixels_per_hectare(info_layer_width_px, map_width_meters)
        coordinate_scale: float = map_width_meters / info_layer_width_px

        farmland_numbers: list[int] = [
            int(v) for v in np.unique(pixels) if int(v) not in unbuyable_values
        ]

        result: dict[int, dict] = {}

        for farmland_number in farmland_numbers:
            mask: np.ndarray = pixels == farmland_number
            pixel_count: int = int(mask.sum())

            if pixel_count == 0:
                continue

            result[farmland_number] = {
                "coordinates": self._largest_contour(mask, coordinate_scale),
                "size_ha": round(pixel_count / pixels_per_hectare, 2),
            }

        return result

    @staticmethod
    def _pixels_per_hectare(image_width_px: int, map_width_meters: int) -> float:
        """
        Calculate how many pixels make up one hectare, based on the
        map's real-world width relative to the info layer's resolution.

        :param image_width_px: Width of the farmlands PNG in pixels.
        :param map_width_meters: The map's pixel width in meters.
        :return: Pixels per hectare.
        :raises ZeroDivisionError: If image_width_px is 0 (corrupt/empty image).
        """
        meters_per_pixel: float = map_width_meters / image_width_px
        return 10_000 / (meters_per_pixel ** 2)

    @staticmethod
    def _largest_contour(
            mask: np.ndarray,
            coordinate_scale: float = 1.0
    ) -> list[list[int]] | None:
        """
        Find the largest polygon boundary within a farmland's pixel mask.
        Only the largest contour is kept as a storage optimisation.

        Note: Farmlands split across multiple disconnected areas will lose its smaller pieces.

        :param mask: Boolean pixel mask for a single farmland.
        :param coordinate_scale: Multiplier is applied to every vertex to
            convert from the farmlands PNG's own pixel space into the
            map's width/height space (see _extract_geometry). 1.0 for
            maps where the farmlands PNG already matches the map size.
        :return: List of [x, y] polygon vertices, or None if no contour was found.
        :raises cv2.error: If OpenCV fails to process the mask.
        """
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        largest = max(contours, key=len)
        simplified = cv2.approxPolyDP(largest, CONTOUR_EPSILON, True)
        coordinates: list = simplified.squeeze().tolist()

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
        return FarmlandBuilder._bounding_box_from_coords(f.coordinates for f in farmlands)

    @staticmethod
    def _bounding_box_from_coords(coordinate_lists: Iterable[list]) -> dict:
        """
        Compute the combined min/max x/y bounds across several coordinate lists.

        :param coordinate_lists: Iterable of coordinate lists, each a list of [x, y] pairs.
        :return: {"min_x", "min_y", "max_x", "max_y"}, or all None if empty.
        """
        coordinate_lists = list(coordinate_lists)
        xs: list[int] = [x for coords in coordinate_lists for x, _ in coords]
        ys: list[int] = [y for coords in coordinate_lists for _, y in coords]
        if not xs:
            return {"min_x": None, "min_y": None, "max_x": None, "max_y": None}
        return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}
