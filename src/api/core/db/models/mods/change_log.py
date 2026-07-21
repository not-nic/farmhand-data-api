from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import JSON, UUID, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map

from src.api.core.db.models._model_base import SqlAlchemyBase


class ChangeLog(SqlAlchemyBase):
    """
    A single versioned changelog entry extracted from a map's description text.

    Each map has many changelog entries, one per version the author has
    released.
    """

    __tablename__ = "map_changelogs"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maps.id"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    requires_new_savegame: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    map: Mapped[Map] = relationship("Map", back_populates="changelogs")
