"""
Python module containing the dependency database model.
"""

from uuid import uuid7

from sqlalchemy import UUID, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from src.api.core.db.models._model_base import SqlAlchemyBase

map_dependencies = Table(
    "map_dependencies",
    SqlAlchemyBase.metadata,
    Column("map_id", ForeignKey("maps.id"), primary_key=True),
    Column("dependency_id", UUID, ForeignKey("mod_dependencies.id"), primary_key=True),
)


class Dependency(SqlAlchemyBase):
    """
    a mod_dependencies table to list the dependencies required for
    each mod/map.

    Attributes:
        id: a UUID of the dependency
        mod_id: The Name of the Dependency.
    """
    __tablename__ = "mod_dependencies"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    mod_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

