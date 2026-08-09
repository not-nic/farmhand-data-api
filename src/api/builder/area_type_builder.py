"""
Python module containing a builder to compute per-farmland area type
composition from a converted infoLayer_environment.grle / .png.
"""

import time

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from src.api.constants import AreaType, IngestionStatus
from src.api.core.db.models import Farmland, InfoLayer, Map
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.builder.base_layer_builder import (
    BaseMapLayerBuilder,
    ENVIRONMENT_LAYER_KEY,
    FARMLANDS_LAYER_KEY,
)


class AreaTypeBuilder(BaseMapLayerBuilder):
    """
    Builds per-farmland area type composition (Open Land, City, Village,
    Harbor, Industrial, Open Water) from a converted environment .grle.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.farmland_repository = FarmlandRepository(db)

    def process_pending(self) -> None:
        """
        Compute and persist area type composition for every farmland
        that doesn't have it yet. Maps whose farmlands or environment
        layer haven't finished converting are skipped and retried on
        a later pass, rather than erroring.
        """
        pending: list[Farmland] = self.farmland_repository.get_pending_area_types()

        if not pending:
            return

        map_ids: set[int] = {farmland.map_id for farmland in pending}

        for map_id in map_ids:
            farmlands_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
                map_id, FARMLANDS_LAYER_KEY
            )
            environment_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
                map_id, ENVIRONMENT_LAYER_KEY
            )

            if not farmlands_layer or not farmlands_layer.is_ingested:
                continue
            if not environment_layer or not environment_layer.is_ingested:
                continue

            try:
                self._process_map(map_id)
            except Exception as exc:
                logger.error(
                    "[%s]: Failed to compute area types for map %d: %s",
                    self.name,
                    map_id,
                    exc,
                )

    def _process_map(self, map_id: int) -> None:
        """
        Compute and persist area type composition for every pending
        farmland on a single map.

        :param map_id: The map to process.
        :raises ValueError: If required layer or map data isn't available yet.
        :raises ClientError: If an S3 fetch fails.
        :raises ParseError: If map.i3d is not valid XML.
        :raises UnidentifiedImageError: If a layer's PNG is unreadable.
        """
        started_at: float = time.perf_counter()
        composition: dict[int, dict[str, float]] = self.get_area_type_composition(map_id)

        farmlands: list[Farmland] = [
            f for f in self.farmland_repository.get_pending_area_types() if f.map_id == map_id
        ]

        found_count: int = 0
        for farmland in farmlands:
            area_types: dict[str, float] | None = composition.get(farmland.number)

            if not area_types:
                self.farmland_repository.update(farmland, area_types={})
                continue

            self.farmland_repository.update(farmland, area_types=area_types)
            found_count += 1

        elapsed: float = time.perf_counter() - started_at
        logger.info(
            "[%s]: Map %d — %d/%d farmland(s) area types computed in %.2fs.",
            self.name,
            map_id,
            found_count,
            len(farmlands),
            elapsed,
        )

    def get_area_type_composition(self, map_id: int) -> dict[int, dict[str, float]]:
        """
        Determine what percentage of each farmland is covered by an area
        type (e.g. Open Land, City, Industrial).

        :param map_id: The map to compute area type composition for.
        :return: {farmland_number: {area_type_key: percentage}}
        :raises ValueError: If required layer or map data isn't available yet.
        :raises ClientError: If an S3 fetch fails.
        :raises ParseError: If map.i3d is not valid XML.
        :raises UnidentifiedImageError: If a layer's PNG is unreadable.
        """
        map_obj: Map | None = self.map_service.get_map_by_id(map_id)

        if not map_obj or not map_obj.information or not map_obj.information.width:
            raise ValueError(f"Map {map_id} has no terrain width available.")

        if map_obj.ingestion_status == IngestionStatus.FAILED:
            raise ValueError(f"Map {map_id} ingestion status is FAILED.")

        parsed_i3d = self._parse_i3d(map_obj)

        if parsed_i3d is None:
            raise ValueError(f"Could not fetch or parse map.i3d for map {map_id}.")

        area_type_group = self._get_area_type_group(parsed_i3d)

        if area_type_group is None:
            raise ValueError(f"No environment Area Type group found for map {map_id}.")

        farmlands_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
            map_id, FARMLANDS_LAYER_KEY
        )
        environment_layer: InfoLayer | None = self.info_layer_repository.get_by_map_and_key(
            map_id, ENVIRONMENT_LAYER_KEY
        )

        if not farmlands_layer or not farmlands_layer.is_ingested:
            raise ValueError(f"Farmlands layer not yet ingested for map {map_id}.")
        if not environment_layer or not environment_layer.is_ingested:
            raise ValueError(f"Environment layer not yet ingested for map {map_id}.")

        farmlands_pixels: np.ndarray = self._load_pixels(
            self.aws_service.get_content_from_uri(farmlands_layer.asset_uri)
        )
        environment_pixels: np.ndarray = self._load_pixels(
            self.aws_service.get_content_from_uri(environment_layer.asset_uri)
        )

        if environment_pixels.shape != farmlands_pixels.shape:
            environment_image = Image.fromarray(environment_pixels).resize(
                (farmlands_pixels.shape[1], farmlands_pixels.shape[0]), Image.Resampling.NEAREST
            )
            environment_pixels = np.array(environment_image)

        mask: int = (1 << area_type_group.num_channels) - 1
        area_type_pixels: np.ndarray = (
            environment_pixels.astype(np.int32) >> area_type_group.first_channel
        ) & mask

        area_type_names: dict[int, str] = {
            option.value: option.name for option in area_type_group.options
        }

        composition: dict[int, dict[str, float]] = {}

        for farmland_number in np.unique(farmlands_pixels):
            farmland_mask = farmlands_pixels == farmland_number
            total_pixels = int(farmland_mask.sum())

            if total_pixels == 0:
                continue

            area_values, counts = np.unique(area_type_pixels[farmland_mask], return_counts=True)

            composition[int(farmland_number)] = {
                self._area_type_key(area_type_names.get(int(area_value))): round(
                    (count / total_pixels) * 100, 2
                )
                for area_value, count in zip(area_values, counts)
            }

        return composition

    @staticmethod
    def _area_type_key(raw_name: str | None) -> str:
        """
        Convert a raw Area Type display name into its enum key for
        storage/API output, e.g. 'Open Land' -> 'farmland'. Uses the
        enum's member name rather than its value, since AreaType is a
        StrEnum and its value IS the raw display string — relying on
        default serialization would just reproduce 'Open Land' as-is.

        :param raw_name: The raw display name from the i3d Option list.
        :return: Snake_case area type key, or 'unknown' if unrecognised.
        """
        try:
            area_type = AreaType(raw_name) if raw_name else AreaType.UNKNOWN
        except ValueError:
            area_type = AreaType.UNKNOWN

        return area_type.name.lower()
