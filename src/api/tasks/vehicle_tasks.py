"""
Tasks for processing vehicle data in the background.
"""

from src.api.core.db.db_setup import db_session
from src.api.core.logger import logger
from src.api.services.vehicles.vehicle_asset_ingestion_service import VehicleAssetIngestionService


def generate_vehicle_assets() -> None:
    """
    Background task to convert pending vehicle store images into .png
    images in the assets bucket.
    """
    with db_session() as db:
        logger.debug("[VEHICLE TASKS]: Generating pending vehicle assets.")
        VehicleAssetIngestionService(db).process_pending()
