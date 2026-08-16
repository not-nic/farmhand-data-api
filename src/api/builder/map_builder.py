"""
Python module containing a MapBuilder, which coordinates a set of
layer builders(e.g. farmland, environment, soil maps) that each
transform .i3d and infoLayer data into a 'map'.

The resulting map data can be queried via the farmhand APIs and
rendered on the frontend.
"""

from sqlalchemy.orm import Session

from src.api.builder.base_layer_builder import BaseMapLayerBuilder
from src.api.builder.environment_builder import EnvironmentBuilder
from src.api.builder.farmland_builder import FarmlandBuilder
from src.api.core.db.models import Map
from src.api.core.exceptions import MapBuilderError
from src.api.core.logger import logger
from src.api.core.schema.mods.i3d import I3dModel
from src.api.parsers.xml.i3d_parser import I3dParser
from src.api.services.aws.aws_service import AwsService
from src.api.services.maps.map_service import MapService


class MapBuilder:
    """
    MapBuilder class used to create map data from infoLayer .grle files and the map i3d.
    """

    def __init__(self, db: Session) -> None:
        self.map_service = MapService(db)
        self.aws_service = AwsService()

        self.farmland_builder: FarmlandBuilder = FarmlandBuilder(db)
        self.environment_builder: EnvironmentBuilder = EnvironmentBuilder(db)

        self.builders: list[BaseMapLayerBuilder] = [
            self.farmland_builder,
            self.environment_builder,
        ]

    def get_pending_map_ids(self) -> set[int]:
        """
        Get the union of every builder's pending map ids.
        :return: Set of map ids with pending work for at least one builder.
        """
        map_ids: set[int] = set()
        for builder in self.builders:
            try:
                map_ids = map_ids.union(builder.get_pending_map_ids())
            except MapBuilderError as exc:
                logger.exception(exc)

        return map_ids

    def build(self, map_obj: Map) -> list[str]:
        """
        Fetch and parse a map's i3d, then run every registered builder
        against it.

        :param map_obj: The map to process.
        :return: Collected error messages from failed builders.
        """
        parsed_i3d = self._parse_i3d(map_obj)
        errors: list[str] = []

        for builder in self.builders:
            try:
                builder.process_map(map_obj, parsed_i3d)
            except MapBuilderError as exc:
                logger.exception(exc)
                errors.append(str(exc))

        return errors

    def _parse_i3d(self, map_obj: Map) -> I3dModel | None:
        """
        Fetch and parse a map's map.i3d file.

        :param map_obj: (Map) The map to fetch map.i3d for.
        :return: (I3dModel) Parsed I3dModel or None if it couldn't be retrieved.
        """
        if not map_obj.data_uri or not map_obj.information or not map_obj.information.map_i3d_filename:
            return None

        filename = map_obj.information.map_i3d_filename
        content = self.aws_service.get_content_from_uri(f"{map_obj.data_uri}/map/{filename}")
        return I3dParser().parse(content)
