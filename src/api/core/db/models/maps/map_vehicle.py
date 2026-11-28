"""
SQLAlchemy model for a vehicle a map starts with.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map
    from src.api.core.db.models.vehicles import (
        Vehicle,
        VehicleFillUnitConfiguration,
        VehicleMotorConfiguration,
    )

from src.api.core.db.models._model_base import SqlAlchemyBase


class MapVehicle(SqlAlchemyBase):
    """
    Database model linking a map's vehicles.xml entry to a catalogue vehicle
    and its selected configurations.

    Attributes:
        id: UUID7 primary key.
        map_id: Foreign key to the parent Map.
        vehicle_id: Foreign key to the catalogue Vehicle.
        motor_configuration_id: Foreign key to the selected motor configuration.
        fill_unit_configuration_id: Foreign key to the selected fill unit configuration.

    Only vehicles the player's farm owns at the start of a save are stored.
    """

    __tablename__ = "map_vehicles"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("vehicles.id"), nullable=False)
    motor_configuration_id: Mapped[UUID | None] = mapped_column(
        UUID, ForeignKey("vehicle_motor_configurations.id", ondelete="SET NULL"), nullable=True
    )
    fill_unit_configuration_id: Mapped[UUID | None] = mapped_column(
        UUID, ForeignKey("vehicle_fill_unit_configurations.id", ondelete="SET NULL"), nullable=True
    )

    map: Mapped[Map] = relationship("Map", back_populates="vehicles")
    vehicle: Mapped[Vehicle] = relationship("Vehicle", lazy="joined")
    motor_configuration: Mapped[VehicleMotorConfiguration | None] = relationship(
        "VehicleMotorConfiguration", lazy="joined"
    )
    fill_unit_configuration: Mapped[VehicleFillUnitConfiguration | None] = relationship(
        "VehicleFillUnitConfiguration", lazy="joined"
    )
