"""
SQLAlchemy model for map farmland.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import JSON, UUID, Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import InfoLayer, Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class Farmland(SqlAlchemyBase):
    """
    Database model for a maps farmland, it combines data from the map.i3d
    file, farmlands.xml, and the infoLayer_farmlands.grle to get farmland
    coordinates and size.

    Attributes:
        id: UUID7 primary key.
        map_id: Foreign key to the parent Map.
        info_layer_id: Foreign key to the farmlands InfoLayer.
        number: The farmland number.
        price_per_ha: The price of the farmland per hectare.
        price_scale: Price multiplier for each farmland.
        default: Whether this farmland is owned at the start of a new save.
        coordinates: Polygon vertex data.
        size_ha: Farmland area in hectares.
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
    area_types: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)

    map: Mapped[Map] = relationship("Map", back_populates="farmlands")
    info_layer: Mapped[InfoLayer] = relationship("InfoLayer")
