"""
SQLAlchemy model for a map's parsed maps.xml information.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class MapInformation(SqlAlchemyBase):
    """
    SQLAlchemy model for the maps.xml information, contains the file names
    of XML configuration files used within the map and some basic information
    like width, and height.

    Attributes:
        id: UUID primary key.
        map_id: Foreign key to the parent Map.
        width: width in pixels.
        height: height in pixels.
        map_i3d_filename: Filename of the map's main .i3d file.
        farmlands_filename: Filename of the farmlands config XML.
        fields_filename: Filename of the fields config XML.
        fill_types_filename: Filename of the fill types config XML.
    """

    __tablename__ = "map_information"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maps.id"), nullable=False, unique=True, index=True
    )

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    map_i3d_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    farmlands_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fields_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fill_types_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    map: Mapped[Map] = relationship("Map", back_populates="information")
