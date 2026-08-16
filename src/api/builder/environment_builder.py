"""
Python module containing a 'map' builder component to compute the environment
layers (Open Land, Cities, Villages, Harbour, Industrial, Water) for each farmland
within a given map.
"""

import time

import numpy as np
from botocore.exceptions import ClientError
from PIL import Image
from sqlalchemy.orm import Session

from src.api.builder.base_layer_builder import (
    ENVIRONMENT_LAYER_KEY,
    FARMLANDS_LAYER_KEY,
    BaseMapLayerBuilder,
)
from src.api.constants import AreaType
from src.api.core.db.models import Farmland, Map
from src.api.core.exceptions import LayerNotReadyError, MapBuilderError
from src.api.core.logger import logger
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.schema.mods.i3d import I3dModel, InfoLayerGroupModel


class EnvironmentBuilder(BaseMapLayerBuilder):
    """
    Class to create an environment area type for each farmland within a
    given map using a converted 'infoLayer_environment.grle'
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.farmland_repository = FarmlandRepository(db)

    def get_pending_map_ids(self) -> set[int]:
        """
        Get the ids of every map with farmlands awaiting area types.
        :return: Set of map ids awaiting processing.
        """
        pending: list[Farmland] = self.farmland_repository.get_pending_environment()
        return {farmland.map_id for farmland in pending}

    def process_map(self, map_obj: Map, parsed_i3d: I3dModel | None) -> None:
        """
        Compute and persist area type composition for a given map.

        :param map_obj: (int) The map to process.
        :param parsed_i3d: (I3dModel) The map's already-parsed I3dModel, or None if
            it couldn't be fetched/parsed.
        """
        map_id = map_obj.id
        farmlands: list[Farmland] = [
            f for f in self.farmland_repository.get_pending_environment() if f.map_id == map_id
        ]

        if not farmlands:
            return

        started_at: float = time.perf_counter()

        try:
            composition = self._compute_composition(map_id, parsed_i3d)
        except LayerNotReadyError as exc:
            logger.debug("[%s]: Skipping map %d — %s", self.name, map_id, exc)
            return
        except ValueError as exc:
            raise MapBuilderError(
                f"{self.name} failed to compute area types for map {map_id}."
            ) from exc
        except ClientError as exc:
            raise MapBuilderError(
                f"{self.name} failed to fetch a layer for map {map_id}."
            ) from exc

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

    def _compute_composition(
        self, map_id: int, parsed_i3d: I3dModel | None
    ) -> dict[int, dict[str, float]]:
        """
        Method to determine what percentage of each farmland is covered by an area type.

        :param map_id: (int) The map to process.
        :return: (dict[str, float]) a farmland and its area type percentage
            Example:
                {farmland_number: {area_type_key: percentage}}
        """
        if parsed_i3d is None:
            raise ValueError(f"Could not fetch or parse map.i3d for map {map_id}.")

        area_type_group = self._resolve_area_type_group(parsed_i3d, map_id)

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

    @staticmethod
    def _resolve_area_type_group(parsed_i3d: I3dModel, map_id: int) -> InfoLayerGroupModel:
        """
        Resolve the environment layer's 'Area Type' group for a map.

        :param map_id: (int) The map to process.
        :return: (InfoLayerGroupModel) The Area Type InfoLayerGroupModel.
        """
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

        :param map_id: (int) The map id of the layer.
        :param layer_key: (str) The layer key to load, e.g. FARMLANDS_LAYER_KEY.
        :return: (np.ndarray) The layer's pixels.
        """
        layer = self.info_layer_repository.get_by_map_and_key(map_id, layer_key)

        if not layer or not layer.is_ingested:
            raise LayerNotReadyError(f"{layer_key} layer not yet ingested for map {map_id}.")

        return self._load_pixels(self.aws_service.get_content_from_uri(layer.asset_uri))

    @staticmethod
    def _match_shape(pixels: np.ndarray, target: np.ndarray) -> np.ndarray:
        """
        Nearest-neighbour resizes `pixels` to `target`'s shape if they differ.

        :param pixels: (np.ndarray) The pixels to resize.
        :param target: (np.ndarray) The array whose shape should be matched.
        :return: (np.ndarray) pixels resized to `target`'s shape where necessary.
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

        :param raw_name: (str) The raw display name from the i3d Option list.
        :return: (str) Snake_case area type key, or 'unknown' if unrecognised.
        """
        try:
            area_type = AreaType(raw_name) if raw_name else AreaType.UNKNOWN
        except ValueError:
            area_type = AreaType.UNKNOWN

        return area_type.name.lower()
