"""
Pydantic response models for vehicles.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from src.api.constants import AssetType, VehicleCategory
from src.api.core.db.models import Vehicle
from src.api.core.schema.assets.assets import AssetResponse


def category_label(vehicle: Vehicle) -> str | None:
    """
    :param vehicle: A given Vehicle database object.
    :return: The curated display text for the vehicle's category, e.g. "Medium Tractors".
        Falls back to the stored category_label (e.g. a stale singular label from before
        pluralisation, for rows that have not been re-ingested) and then the raw key.
    """
    category = VehicleCategory.from_key(vehicle.category or "")
    return (
        (category and category.value)
        or vehicle.category_label
        or vehicle.category
    )


class VehicleCategoryResponseModel(BaseModel):
    """
    A vehicle shop category, pairing its URL-safe slug with its display label.
    """

    slug: str
    label: str


def icon_uri(vehicle: Vehicle) -> str | None:
    """
    :param vehicle: A given Vehicle database object.
    :return: S3 URI of the vehicle's converted store icon, for the /assets/resolve endpoint,
        or None if it has not been ingested yet.
    """
    return next(
        (
            asset.asset_uri
            for asset in vehicle.assets
            if asset.asset_type == AssetType.ICON and asset.is_ingested
        ),
        None,
    )


class MotorConfigurationResponseModel(BaseModel):
    """
    A motor configuration of a vehicle.
    """

    name: str | None = None
    vehicle_name: str | None = None
    hp: int | None = None
    max_speed: int | None = None
    price: int | None = None

    model_config = ConfigDict(from_attributes=True)


class FillUnitResponseModel(BaseModel):
    """
    A single fill unit with the display text of its fill types.
    """

    fill_types: list[str] = []
    capacity: float = 0.0

    @field_validator("fill_types", mode="before")
    @classmethod
    def to_labels(cls, value: list) -> list[str]:
        """
        :param value: Stored fill types, each {"key": "FERTILIZER", "label": "Solid Fertilizer"}.
        :return: The labels, e.g. ["Solid Fertilizer"].
        """
        return [t.get("label") or t.get("key") if isinstance(t, dict) else t for t in value]


class FillUnitConfigurationResponseModel(BaseModel):
    """
    A fill unit configuration of a vehicle.

    Attributes:
        name: The shop option name, e.g. "Seeds 2000 | Fertilizer 3000",
            or None when the vehicle has a single unnamed option.
    """

    name: str | None = None
    price: int | None = None
    fill_units: list[FillUnitResponseModel] = []

    model_config = ConfigDict(from_attributes=True)


class VehicleSpecsResponseModel(BaseModel):
    """
    The in-game specs of a vehicle. Any of these may be None, e.g. tractors
    have no needed_power.

    Attributes:
        weight: The vehicle's weight, in kg.
        working_speed: The vehicle's working speed, in km/h.
        working_width: The vehicle's working width, in metres.
        needed_power: The power needed to operate the vehicle, in hp.
    """

    weight: int | None = None
    working_speed: int | None = None
    working_width: float | None = None
    needed_power: int | None = None

    model_config = ConfigDict(from_attributes=True)


class VehicleResponseModel(BaseModel):
    """
    A Pydantic Model of a vehicle database object.
    """

    id: UUID
    config_path: str
    name: str
    brand: str | None = None
    category: str | None = None
    price: int | None = None
    dlc: str | None = None
    specs: VehicleSpecsResponseModel
    assets: list[AssetResponse] = []
    motor_configurations: list[MotorConfigurationResponseModel] = []
    fill_unit_configurations: list[FillUnitConfigurationResponseModel] = []

    @classmethod
    def from_vehicle(cls, vehicle: Vehicle) -> VehicleResponseModel:
        """
        Create a pydantic model from a Vehicle database object.
        :param vehicle: A given Vehicle database object.
        :return: The vehicle response.
        """
        return cls(
            id=vehicle.id,
            config_path=vehicle.config_path,
            name=vehicle.name,
            brand=vehicle.brand,
            category=category_label(vehicle),
            price=vehicle.price,
            dlc=vehicle.dlc,
            specs=VehicleSpecsResponseModel.model_validate(vehicle),
            assets=[AssetResponse.model_validate(a) for a in vehicle.assets],
            motor_configurations=[
                MotorConfigurationResponseModel.model_validate(m)
                for m in vehicle.motor_configurations
            ],
            fill_unit_configurations=[
                FillUnitConfigurationResponseModel.model_validate(f)
                for f in vehicle.fill_unit_configurations
            ],
        )


class VehiclesResponseModel(BaseModel):
    """
    Pydantic Response Model for all vehicles.
    """

    vehicles: list[VehicleResponseModel]
