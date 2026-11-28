"""
__init__.py for the /vehicles database models.
"""

from .fill_unit_configuration import VehicleFillUnitConfiguration
from .motor_configuration import VehicleMotorConfiguration
from .vehicle import Vehicle

__all__ = ["Vehicle", "VehicleMotorConfiguration", "VehicleFillUnitConfiguration"]
