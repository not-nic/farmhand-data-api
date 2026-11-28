"""
Python module containing the vehicle motor configuration database model.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.vehicles import Vehicle

from src.api.core.db.models._model_base import SqlAlchemyBase


class VehicleMotorConfiguration(SqlAlchemyBase):
    """
    Database model for a motor configuration option of a vehicle.

    Attributes:
        id: UUID7 primary key.
        vehicle_id: Foreign key to the parent Vehicle.
        index: 1-based position, matches the id of a map's `<configuration name="motor">`.
        name: The motor name, e.g. "6R 145".
        vehicle_name: Full vehicle name when this motor is selected, if the XML sets one.
        hp: Engine power in horsepower.
        max_speed: Maximum speed in km/h.
        price: The additional price of this motor configuration.
    """

    __tablename__ = "vehicle_motor_configurations"
    __table_args__ = (UniqueConstraint("vehicle_id", "index", name="uq_vehicle_motor_index"),)

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    vehicle_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vehicle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="motor_configurations")
