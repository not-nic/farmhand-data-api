"""
Python module containing a 'map' builder component to compute the environment
layers (Open Land, Cities, Villages, Harbour, Industrial, Water) for each farmland
within a given map.
"""

import time

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from src.api.builder.base_layer_builder import (
    ENVIRONMENT_LAYER_KEY,
    FARMLANDS_LAYER_KEY,
    BaseMapLayerBuilder,
)
from src.api.constants import AreaType, IngestionStatus
from src.api.core.db.models import Farmland, Map
from src.api.core.exceptions import LayerNotReadyError
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.schema.mods.i3d import InfoLayerGroupModel


class EnvironmentBuilder(BaseMapLayerBuilder):
    """
    Class to create an environment area type for each farmland within a
    given map using a converted 'infoLayer_environment.grle'
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.farmland_repository = FarmlandRepository(db)

    def process_pending(self) -> None:
        """
        Compute and persist the environment composition for every farmland.
        """

        pending: list[Farmland] = self.farmland_repository.get_pending_area_types()

        if not pending:
            return

        by_map: dict[int, list[Farmland]] = {}
        for farmland in pending:
            by_map.setdefault(farmland.map_id, []).append(farmland)

        for map_id, farmlands in by_map.items():
            try:
                self._process_map(map_id, farmlands)
            except LayerNotReadyError as exc:
                logger.debug("[%s]: Skipping map %d — %s", self.name, map_id, exc)
            except Exception as exc:
                logger.error(
                    "[%s]: Failed to compute area types for map %d: %s",
                    self.name,
                    map_id,
                    exc,
                )

    def _process_map(self, map_id: int, farmlands: list[Farmland]) -> None:
        """
        Compute and persist environment composition for a given map and its farmlands.

        :param map_id: (int) The map to process.
        :param farmlands: (list) The map's farmlands.
        :raises LayerNotReadyError: If a required layer hasn't finished converting.
        :raises ValueError: If map data isn't available yet.
        :raises ClientError: If an S3 fetch fails.
        :raises ParseError: If map.i3d is not valid XML.
        :raises UnidentifiedImageError: If a layer's PNG is unreadable.
        """
        started_at: float = time.perf_counter()
        composition: dict[int, dict[str, float]] = self.get_environment_composition(map_id)

        found_count: int = 0
        for farmland in farmlands:
            area_types: dict[str, float] = composition.get(farmland.number) or {}
            self.farmland_repository.update(farmland, area_types=area_types)
            found_count += bool(area_types)

        elapsed: float = time.perf_counter() - started_at
        logger.info(
            "[%s]: Map %d — %d/%d farmland(s) area types computed in %.2fs.",
            self.name,
            map_id,
            found_count,
            len(farmlands),
            elapsed,
        )

    def get_environment_composition(self, map_id: int) -> dict[int, dict[str, float]]:
        """
        Determine what percentage of each farmland is covered by an area type.

        :param map_id: (int) The map to process.
        :return: (dict[str, float]) a farmland and its area type percentage
            Example:
                {farmland_number: {area_type_key: percentage}}
        """
        area_type_group = self._resolve_area_type_group(map_id)

        farmlands_pixels = self._load_layer_pixels(map_id, FARMLANDS_LAYER_KEY)
        environment_pixels = self._match_shape(
            self._load_layer_pixels(map_id, ENVIRONMENT_LAYER_KEY), farmlands_pixels
        )

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

            area_values, counts = np.unique(area_type_pixels[farmland_mask], return_counts=True)

            composition[int(farmland_number)] = {
                self._area_type_key(area_type_names.get(int(area_value))): round(
                    (count / total_pixels) * 100, 2
                )
                for area_value, count in zip(area_values, counts, strict=True)
            }

        return composition

    def _resolve_area_type_group(self, map_id: int) -> InfoLayerGroupModel:
        """
        Resolve the environment layer's 'Area Type' group for a map.

        :param map_id: (int) The map to process.
        :return: The Area Type InfoLayerGroupModel.
        :raises ValueError: If the map or its i3d file is unavailable.
        """
        map_obj: Map | None = self.map_service.get_map_by_id(map_id)

        if not map_obj:
            raise ValueError(f"Map {map_id} not found.")

        if map_obj.ingestion_status == IngestionStatus.FAILED:
            raise ValueError(f"Map {map_id} ingestion status is FAILED.")

        parsed_i3d = self._parse_i3d(map_obj)

        if parsed_i3d is None:
            raise ValueError(f"Could not fetch or parse map.i3d for map {map_id}.")

        for layer in parsed_i3d.info_layers:
            if layer.layer_key != ENVIRONMENT_LAYER_KEY:
                continue
            for group in layer.groups:
                if group.name == "Area Type":
                    return group

        raise ValueError(f"No environment Area Type group found for map {map_id}.")

    def _load_layer_pixels(self, map_id: int, layer_key: str) -> np.ndarray:
        """
        Load an environment info layer.

        :param map_id: The map id of the layer.
        :param layer_key: The layer key to load, e.g. FARMLANDS_LAYER_KEY.
        :return: The layer's pixels.
        :raises LayerNotReadyError: If the layer is missing or not yet ingested.
        """
        layer = self.info_layer_repository.get_by_map_and_key(map_id, layer_key)

        if not layer or not layer.is_ingested:
            raise LayerNotReadyError(f"{layer_key} layer not yet ingested for map {map_id}.")

        return self._load_pixels(self.aws_service.get_content_from_uri(layer.asset_uri))

    @staticmethod
    def _match_shape(pixels: np.ndarray, target: np.ndarray) -> np.ndarray:
        """
        Nearest-neighbour resizes `pixels` to `target`'s shape if they differ.

        :param pixels: The pixels to resize.
        :param target: The array whose shape should be matched.
        :return: `pixels`, resized to `target`'s shape where necessary.
        """
        if pixels.shape == target.shape:
            return pixels

        resized = Image.fromarray(pixels).resize(
            (target.shape[1], target.shape[0]), Image.Resampling.NEAREST
        )

        return np.array(resized)

    @staticmethod
    def _area_type_key(raw_name: str | None) -> str:
        """
        Convert a raw farming simulator area type into an enum used
        by the farmhand-data-api.

        :param raw_name: The raw display name from the i3d Option list.
        :return: Snake_case area type key, or 'unknown' if unrecognised.
        """
        try:
            area_type = AreaType(raw_name) if raw_name else AreaType.UNKNOWN
        except ValueError:
            area_type = AreaType.UNKNOWN

        return area_type.name.lower()
