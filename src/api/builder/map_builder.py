"""
Python module containing MapBuilder, which orchestrates every
registered map layer builder. Add a new builder here to add a new
derived data layer (soil composition, fields, etc.), without growing
any individual builder.
"""

from sqlalchemy.orm import Session

from src.api.builder.area_type_builder import AreaTypeBuilder
from src.api.builder.base_layer_builder import BaseMapLayerBuilder
from src.api.builder.farmland_builder import FarmlandBuilder
from src.api.core.logger import logger


class MapBuilder:
    """
    Runs every registered map layer builder's process_pending().
    """

    def __init__(self, db: Session) -> None:
        self.farmland_builder: FarmlandBuilder = FarmlandBuilder(db)
        self.area_type_builder: AreaTypeBuilder = AreaTypeBuilder(db)

        self.builders: list[BaseMapLayerBuilder] = [
            self.farmland_builder,
            self.area_type_builder,
        ]

    def process_pending(self) -> None:
        """
        Run every registered builder's pending work, in order. A
        builder that fails unexpectedly is logged and skipped, so one
        broken layer doesn't prevent the others from running.
        """
        for builder in self.builders:
            try:
                builder.process_pending()
            except Exception:
                logger.exception(
                    "[MapBuilder]: %s.process_pending() failed unexpectedly.",
                    builder.name,
                )
