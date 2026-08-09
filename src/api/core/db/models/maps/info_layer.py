"""
SQLAlchemy model for a map's GRLE info layers.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class InfoLayer(SqlAlchemyBase):
    """
    A single info layer referenced in a map's i3d file, e.g. farmlands
    or soilMap.

    Attributes:
        id: UUID7 primary key.
        map_id: Foreign key to the parent Map.
        layer_key: Matches the InfoLayer/infoLayer name, e.g. 'farmlands', 'soilMap'.
        grle_filename: Filename of the source GRLE, e.g. infoLayer_farmlands.grle.
        i3d_file_id: fileId referenced in map.i3d for this layer.
    """

    __tablename__ = "map_info_layers"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(Integer, ForeignKey("maps.id"), nullable=False, index=True)

    layer_key: Mapped[str] = mapped_column(String(100), nullable=False)
    i3d_file_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grle_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_ingested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    map: Mapped[Map] = relationship("Map", back_populates="info_layers")
