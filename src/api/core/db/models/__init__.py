"""
__init__.py module containing the imports for all database models, so that
they can be imported by:
    from src.api.core.db.models import Map, etc.
"""

from src.api.core.db.models.assets import Asset
from src.api.core.db.models.maps import Farmland, InfoLayer, Map, MapInformation, MapVehicle
from src.api.core.db.models.mods import Dependency, ModDescription
from src.api.core.db.models.vehicles import (
    Vehicle,
    VehicleFillUnitConfiguration,
    VehicleMotorConfiguration,
)

__all__ = [
    "Map",
    "Farmland",
    "InfoLayer",
    "MapInformation",
    "ModDescription",
    "Dependency",
    "Asset",
    "Vehicle",
    "VehicleMotorConfiguration",
    "VehicleFillUnitConfiguration",
    "MapVehicle",
]

