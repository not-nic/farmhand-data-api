"""
__init__.py for the /vehicles pydantic models.
"""

from .ingest import VehicleIngestResult
from .map_vehicles import MapVehicleModel
from .store_items import StoreItemModel
from .vehicle import (
    FillUnitConfigurationResponseModel,
    FillUnitResponseModel,
    MotorConfigurationResponseModel,
    VehicleCategoryResponseModel,
    VehicleResponseModel,
    VehicleSpecsResponseModel,
    VehiclesResponseModel,
)
from .vehicle_xml import (
    FillUnitConfigModel,
    FillUnitModel,
    MotorConfigModel,
    VehicleXmlModel,
)

__all__ = [
    "VehicleIngestResult",
    "MapVehicleModel",
    "StoreItemModel",
    "VehicleXmlModel",
    "MotorConfigModel",
    "FillUnitConfigModel",
    "FillUnitModel",
    "VehicleCategoryResponseModel",
    "VehicleResponseModel",
    "VehiclesResponseModel",
    "VehicleSpecsResponseModel",
    "MotorConfigurationResponseModel",
    "FillUnitConfigurationResponseModel",
    "FillUnitResponseModel",
]
