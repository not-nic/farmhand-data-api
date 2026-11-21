"""
Python module containing the vehicle fill unit configuration database model.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import JSON, UUID, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.vehicles import Vehicle

from src.api.core.db.models._model_base import SqlAlchemyBase


class VehicleFillUnitConfiguration(SqlAlchemyBase):
    """
    Database model for a fill unit configuration option of a vehicle.

    Attributes:
        id: UUID7 primary key.
        vehicle_id: Foreign key to the parent Vehicle.
        index: 1-based position, matches the id of a map's `<configuration name="fillUnit">`.
        name: The configuration name.
        price: The additional price of this configuration.
        fill_units: List of {"fill_types": [...], "capacity": float}.
    """

    __tablename__ = "vehicle_fill_unit_configurations"
    __table_args__ = (UniqueConstraint("vehicle_id", "index", name="uq_vehicle_fill_unit_index"),)

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    vehicle_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fill_units: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="fill_unit_configurations")
