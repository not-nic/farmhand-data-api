"""
Python module containing the vehicle database model.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.assets import Asset
    from src.api.core.db.models.vehicles import (
        VehicleFillUnitConfiguration,
        VehicleMotorConfiguration,
    )

from src.api.core.db.models._model_base import SqlAlchemyBase


class Vehicle(SqlAlchemyBase):
    """
    Database model for a base game or DLC Farming Simulator vehicle.

    Attributes:
        id: UUID7 primary key.
        config_path: Canonical config path, e.g. "vehicles/fendt/vario700/vario700.xml".
        name: The vehicle's display name.
        brand: The vehicle's display brand.
        category: Raw shop category, e.g. "TRACTORSM".
        category_label: Display text of the category, e.g. "Medium Tractor".
        vehicle_type: Raw root type attribute of the vehicle XML, e.g. "tractor".
        price: The in-game price of the vehicle.
        dlc: The DLC title, or None for the base game.
        image: Path to the vehicle's store image.
        weight: The vehicle's weight, in kg.
        working_speed: Recommended working speed, in km/h.
        working_width: Working width of the tool, in metres.
        needed_power: Power required to use/tow the tool, in hp.
        motor_configurations: Motor configurations ordered by index.
        fill_unit_configurations: Fill unit configurations ordered by index.
        assets: Image assets of the vehicle, e.g. its store icon.

    Required fields when creating a new vehicle: config_path and name.
    """

    __tablename__ = "vehicles"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    config_path: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    category_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dlc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    working_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    working_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    needed_power: Mapped[int | None] = mapped_column(Integer, nullable=True)

    motor_configurations: Mapped[list[VehicleMotorConfiguration]] = relationship(
        "VehicleMotorConfiguration",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        order_by="VehicleMotorConfiguration.index",
    )
    fill_unit_configurations: Mapped[list[VehicleFillUnitConfiguration]] = relationship(
        "VehicleFillUnitConfiguration",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        order_by="VehicleFillUnitConfiguration.index",
    )
    assets: Mapped[list[Asset]] = relationship(
        "Asset",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
