"""
Python module containing the mod description database model.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import UUID, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class ModDescription(SqlAlchemyBase):
    """
    Stores the data parsed from a map's modDesc.xml file.

    Has a one-to-one relationship with Map — each map has at most one
    ModDescription, populated after the XML parsing stage completes.

    Attributes:
        id: UUID7 primary key.
        map_id: Foreign key to the parent Map.
        title: Title of the map.
        description: Description of the map.
        config_filename: Filename of the map's maps.xml config.
        vehicles_filename: Filename of the default vehicles XML.
        placeables_filename: Filename of the default placeables XML.
        items_filename: Filename of the default items XML.
    """

    __tablename__ = "mod_descriptions"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maps.id"), nullable=False, unique=True, index=True
    )

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    map_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    config_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vehicles_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    placeables_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    items_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    map: Mapped[Map] = relationship("Map", back_populates="mod_description")

