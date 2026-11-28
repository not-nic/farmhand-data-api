"""
Pydantic models for data parsed from a Farming Simulator vehicle XML file.
"""

from pydantic import BaseModel, Field


class MotorConfigModel(BaseModel):
    """
    A motor configuration of a vehicle. Index is the 1-based position.
    """

    index: int
    name: str | None = None
    vehicle_name: str | None = None
    hp: int | None = None
    max_speed: int | None = None
    price: int | None = None


class FillUnitModel(BaseModel):
    """
    A single fill unit (tank / hopper / bed) of a fill unit configuration.
    Fill types are upper-case keys, e.g. "DIESEL".
    """

    fill_types: list[str] = Field(default_factory=list)
    capacity: float = 0.0


class FillUnitConfigModel(BaseModel):
    """
    A fill unit configuration of a vehicle. Index is the 1-based position.
    """

    index: int
    name: str | None = None
    price: int | None = None
    fill_units: list[FillUnitModel] = Field(default_factory=list)


class VehicleXmlModel(BaseModel):
    """
    Data parsed from a vehicle XML file (after parentFile resolution).

    Attributes:
        vehicle_type: Raw root "type" attribute, e.g. "combineDrivable".
        image: Store image path, e.g. "vehicles/fendt/vario700/store_vario700.png".
        parent_path: Normalised parentFile path if this vehicle is a reskin.
        motor_configurations: Motor configurations in XML order.
        fill_unit_configurations: Fill unit configurations in XML order.
        weight: The vehicle's weight, in kg.
        working_speed: Recommended working speed, in km/h.
        working_width: Working width of the tool, in metres.
        needed_power: Power required to use/tow the tool, in hp.
    """

    vehicle_type: str | None = None
    image: str | None = None
    parent_path: str | None = None
    motor_configurations: list[MotorConfigModel] = Field(default_factory=list)
    fill_unit_configurations: list[FillUnitConfigModel] = Field(default_factory=list)
    weight: int | None = None
    working_speed: int | None = None
    working_width: float | None = None
    needed_power: int | None = None
