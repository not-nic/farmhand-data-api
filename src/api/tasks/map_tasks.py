"""
Tasks for ingesting maps into the farmhand data-api in the background.
"""

from src.api.core.db.db_setup import db_session
from src.api.core.logger import logger
from src.api.services.map_service import MapService


async def get_new_maps():
    """
    Background task to get new maps from the Farming Simulator ModHub,
    store them in a bucked and parse the required files.
    """
    with db_session() as db:
        logger.info(
            "[MAP TASKS]: Starting background task to retrieve "
            "and download new maps from the ModHub."
        )
        map_service = MapService(db=db)
        await map_service.get_new_maps()
