"""
Python module containing a 'map' builder component to create farmlands from a
given map and its 'infoLayer_farmlands.grle'.
"""

import time
from collections.abc import Iterable

import cv2
import numpy as np
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from src.api.builder.base_layer_builder import (
    FARMLANDS_LAYER_KEY,
    BaseMapLayerBuilder,
)
from src.api.core.db.models import Farmland, InfoLayer, Map
from src.api.core.exceptions import MapBuilderError
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.schema.mods.i3d import I3dModel


class FarmlandBuilder(BaseMapLayerBuilder):
    """
    Class to create farmlands from a map's 'infoLayer_farmlands.grle' file.
    """

    # The furthest a stored vertex may sit from the farmland boundary.
    CONTOUR_TOLERANCE_METERS: float = 3.0

    # Floor on the above in layer pixels; subpixel tolerance preserves noise.
    MIN_CONTOUR_EPSILON: float = 1.0

    # Vertex ceiling per farmland. Exceeding it simplifies past the tolerance,
    # so it caps pathological boundaries.
    MAX_CONTOUR_VERTICES: int = 250

    # Smallest contour area, in layer pixels, still treated as a field.
    MIN_CONTOUR_PIXELS: int = 24

    # Share of a contour's interior belonging to the farmland. Fields score
    # ~1.0; a value threading between them encircles the map filling little.
    MIN_CONTOUR_FILL_RATIO: float = 0.5

    # Opening kernel width in layer pixels; erases thinner mask features.
    # Raise to 5 for a full-resolution layer.
    OPENING_KERNEL_SIZE: int = 3

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.farmland_repository = FarmlandRepository(db)

    def get_pending_map_ids(self) -> set[int]:
        """
        Get the ids of every map with farmlands awaiting geometry.
        :return: Set of map ids awaiting processing.
        """
        pending: list[Farmland] = self.farmland_repository.get_pending_geometry()
        return {farmland.map_id for farmland in pending}

    def process_map(self, map_obj: Map, parsed_i3d: I3dModel | None) -> None:
        """
        Extract and persist geometry for farmlands on a given map.

        :param map_obj: (Map) The map to process.
        :param parsed_i3d: (I3dModel) The map's already-parsed I3dModel, or None if
            it couldn't be fetched/parsed.
        """
        map_id = map_obj.id
        farmlands: list[Farmland] = [
            f for f in self.farmland_repository.get_pending_geometry() if f.map_id == map_id
        ]

        if not farmlands:
            return

        if not map_obj.information or not map_obj.information.width:
            logger.warning(
                "[%s]: Skipping map %d — no map width available.",
                self.name,
                map_id,
            )
            return

        farmlands_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
            map_id,
            FARMLANDS_LAYER_KEY
        )

        if not farmlands_layer or not farmlands_layer.is_ingested:
            return

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

        started_at: float = time.perf_counter()

        try:
            image_bytes: bytes = self.aws_service.get_content_from_uri(farmlands_layer.asset_uri)
            pixels: np.ndarray = self._load_pixels(image_bytes)
            geometry: dict[int, dict] = self._extract_geometry(
                pixels,
                map_obj.information.width,
                unbuyable_values
            )
        except ClientError as exc:
            raise MapBuilderError(
                f"{self.name} failed to fetch the farmlands layer for map {map_id}."
            ) from exc
        except cv2.error as exc:
            raise MapBuilderError(
                f"{self.name} failed extracting contours for map {map_id}."
            ) from exc

        found_count: int = 0
        for farmland in farmlands:
            farmland_geometry: dict | None = geometry.get(farmland.number)

            if not farmland_geometry or not farmland_geometry["coordinates"]:
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

        :param map_id: (int) The map whose farmlands should be rescaled.
        :param offset_x: (float) X offset to add after scaling.
        :param offset_y: (float) Y offset to add after scaling.
        :param scale_x: (float) X scale factor, applied before the offset.
        :param scale_y: (float) Y scale factor, applied before the offset.
        :return: (dict) with the count affected and before/after bounding boxes.
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
        Extract the coordinates of a map's farmland and its size in hectares.

        :param pixels: (np.ndarray) A farmlands pixel array.
        :param map_width_meters: (int) The map's pixel width that has been scaled into meters.
        :param unbuyable_values: (set[int]) Pixel values to exclude.
        :return: (dict) of the coordinates and the map's size.
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

            coordinates: list[list[int]] = self._field_polygon(mask, coordinate_scale)

            if not coordinates:
                logger.debug(
                    "[%s]: Farmland %d yielded no usable contour from %d pixel(s).",
                    self.name,
                    farmland_number,
                    pixel_count,
                )

            result[farmland_number] = {
                "coordinates": coordinates,
                "size_ha": round(pixel_count / pixels_per_hectare, 2),
            }

        return result

    @staticmethod
    def _pixels_per_hectare(image_width_px: int, map_width_meters: int) -> float:
        """
        Calculate how many pixels make up one hectare, based on the map's width
        relative to the info layer's resolution.

        :param image_width_px: (int) Width of the farmlands PNG in pixels.
        :param map_width_meters: (int) The map's pixel width in meters.
        :return: (float) Pixels per hectare.
        """
        meters_per_pixel: float = map_width_meters / image_width_px
        return 10_000 / (meters_per_pixel ** 2)

    @classmethod
    def _field_polygon(
            cls,
            mask: np.ndarray,
            coordinate_scale: float = 1.0
    ) -> list[list[int]]:
        """
        Find the largest polygon boundary within a map's farmland pixel mask.
        Only one contour is kept to keep the storage size small.

        Note: Farmlands split across multiple disconnected areas will lose its smaller pieces.

        :param mask: (np.ndarray) Boolean pixel mask for a farmland.
        :param coordinate_scale: (float) Meters per farmlands-layer pixel. Scales every
            vertex from the PNG's own pixel space into the map's width/height
            space. 1.0 when the two already match.

        :return: (list) [x, y] polygon vertices, empty if no contour qualified.
        """
        cleaned: np.ndarray = cls._clean_mask(mask)

        contours: tuple[np.ndarray, ...]
        contours, _ = cv2.findContours(
            cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        qualifying: list[np.ndarray] = [
            contour for contour in contours
            if cv2.contourArea(contour) >= cls.MIN_CONTOUR_PIXELS
            and cls._fill_ratio(cleaned, contour) >= cls.MIN_CONTOUR_FILL_RATIO
        ]

        if not qualifying:
            return []

        largest: np.ndarray = max(qualifying, key=cv2.contourArea)
        simplified: np.ndarray = cls._simplify(largest, coordinate_scale)
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

    @classmethod
    def _clean_mask(cls, mask: np.ndarray) -> np.ndarray:
        """
        Remove the 1-2px borders that .grle to .png conversion smears along
        field boundaries. Opening erases features thinner than the kernel and
        leaves the field body untouched.

        :param mask: (np.ndarray) Boolean pixel mask for a farmland.
        :return: (np.ndarray) Cleaned uint8 mask, 0 or 1 per pixel.
        """
        as_uint8: np.ndarray = mask.astype(np.uint8)

        if not cls.OPENING_KERNEL_SIZE:
            return as_uint8

        kernel: np.ndarray = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (cls.OPENING_KERNEL_SIZE, cls.OPENING_KERNEL_SIZE)
        )
        return cv2.morphologyEx(as_uint8, cv2.MORPH_OPEN, kernel)

    @staticmethod
    def _fill_ratio(mask: np.ndarray, contour: np.ndarray) -> float:
        """
        Measure how much of a contour's interior the farmland actually occupies.

        :param mask: (np.ndarray) Cleaned mask for a farmland.
        :param contour: (np.ndarray) Contour to measure.
        :return: (float) The occupied fraction of the contour interior, 0.0 to ~1.0.
        """
        area: float = cv2.contourArea(contour)

        if area <= 0:
            return 0.0

        bounds = cv2.boundingRect(contour)
        x, y, width, height = bounds

        interior: np.ndarray = np.zeros((height, width), dtype=np.uint8)
        cv2.drawContours(interior, [contour], -1, 1, -1, offset=(-x, -y))

        # Slicing the mask to the same window puts both arrays in the same
        # coordinate space, so a bitwise AND leaves only the pixels that are
        # both inside the polygon and belong to this farmland. Dividing that
        # count by the polygon's own area gives the occupied fraction.
        occupied: int = int((mask[y:y + height, x:x + width] & interior).sum())
        return occupied / area

    @classmethod
    def _simplify(cls, contour: np.ndarray, coordinate_scale: float) -> np.ndarray:
        """
        Simplify a contour to within CONTOUR_TOLERANCE_METERS of its true shape.

        :param contour: (np.ndarray) Raw contour from cv2.findContours.
        :param coordinate_scale: (float) Meters per farmlands-layer pixel, used to
            convert the tolerance into the pixel space the contour lives in.
        :return: (np.ndarray) Simplified contour.
        """
        # Tolerance is defined in map meters; approxPolyDP works in layer
        # pixels, so divide by the meters-per-pixel scale to convert.
        epsilon: float = max(
            cls.MIN_CONTOUR_EPSILON, cls.CONTOUR_TOLERANCE_METERS / coordinate_scale
        )

        simplified: np.ndarray = cv2.approxPolyDP(contour, epsilon, True)

        # Bounded: epsilon grows geometrically and any polygon degenerates to
        # three or four points long before it reaches the perimeter.
        perimeter: float = cv2.arcLength(contour, True)
        while len(simplified) > cls.MAX_CONTOUR_VERTICES and epsilon < perimeter:
            epsilon *= 1.5
            simplified = cv2.approxPolyDP(contour, epsilon, True)

        return simplified

    @staticmethod
    def _get_unbuyable_values(parsed_i3d: I3dModel) -> set[int] | None:
        """
        Resolve which pixel value represents unbuyable/reserved area for
        this map.

        Maps typically use the last entry (e.g. value=255) as the non-buyable
        land.

        :param parsed_i3d (I3dModel): The map's parsed I3dModel, from _parse_i3d.
        :return: (set) of pixel values to exclude, or None if it couldn't be resolved.
        """
        for layer in parsed_i3d.info_layers:
            if layer.layer_key != FARMLANDS_LAYER_KEY:
                continue
            for group in layer.groups:
                if group.options:
                    return {0, group.options[-1].value}

        return None

    @staticmethod
    def _bounding_box(farmlands: list[Farmland]) -> dict:
        """
        Compute the combined min/max x/y bounds across a list of farmlands.

        :param farmlands: (list) Farmlands with coordinates.
        :return: (dict) of the min and max x, y values.
        """
        return FarmlandBuilder._bounding_box_from_coords(f.coordinates for f in farmlands)

    @staticmethod
    def _bounding_box_from_coords(coordinate_lists: Iterable[list]) -> dict:
        """
        Compute the combined min/max x/y bounds across coordinate lists.

        :param coordinate_lists: (Iterable[list]) of coordinate lists with [x, y] pairs.
        :return: (dict) of the min and max x, y values.
        """
        coordinate_lists = list(coordinate_lists)
        xs: list[int] = [x for coords in coordinate_lists for x, _ in coords]
        ys: list[int] = [y for coords in coordinate_lists for _, y in coords]
        if not xs:
            return {"min_x": None, "min_y": None, "max_x": None, "max_y": None}
        return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}
