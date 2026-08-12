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
from src.api.core.logger import logger


class MapBuilder:
    """
    Used to create map data from infoLayer files and the map i3d.
    """

    def __init__(self, db: Session) -> None:
        self.farmland_builder: FarmlandBuilder = FarmlandBuilder(db)
        self.environment_builder: EnvironmentBuilder = EnvironmentBuilder(db)

        self.builders: list[BaseMapLayerBuilder] = [
            self.farmland_builder,
            self.environment_builder,
        ]

    def process_pending(self) -> None:
        """
        Run every layer builder to create map information.
        """
        for builder in self.builders:
            try:
                builder.process_pending()
            except Exception:
                logger.exception(
                    "[MapBuilder]: %s.process_pending() failed unexpectedly.",
                    builder.name,
                )
