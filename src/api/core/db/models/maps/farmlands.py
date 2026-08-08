"""
SQLAlchemy model for a single farmland on a map.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, Boolean, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import InfoLayer, Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class Farmland(SqlAlchemyBase):
    """
    A single farmland on a map, combining data from the i3d Option list
    and farmlands.xml. coordinates and size_ha are left null until the
    farmland geometry extraction job backfills them from the converted
    farmlands GRLE/PNG.

    Attributes:
        id: UUID7 primary key.
        map_id: Foreign key to the parent Map.
        info_layer_id: Foreign key to the farmlands InfoLayer.
        number: Option value in i3d == farmland id in xml == GRLE bitmask value.
        price_per_ha: From <farmlands pricePerHa="...">, same for every row on this map.
        price_scale: Per-farmland price multiplier from farmlands.xml.
        default: Whether this farmland is owned at the start of a new save.
        coordinates: Polygon vertex data, null until geometry extraction runs.
        size_ha: Farmland area in hectares, null until geometry extraction runs.
    """

    __tablename__ = "map_farmlands"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(Integer, ForeignKey("maps.id"), nullable=False, index=True)
    info_layer_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("map_info_layers.id"), nullable=False)

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_ha: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_scale: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    coordinates: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    size_ha: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    map: Mapped[Map] = relationship("Map", back_populates="farmlands")
    info_layer: Mapped[InfoLayer] = relationship("InfoLayer")
