"""
SQLAlchemy model for a farmhand Asset.
"""

from uuid import uuid7

from sqlalchemy import UUID, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.api.constants import AssetType, EntityType
from src.api.core.db.models._model_base import SqlAlchemyBase


class Asset(SqlAlchemyBase):
    """
    Model of farmhand asset and their asset locations.

    Attributes:
        id: primary key.
        entity_type: The type of entity that owns this asset.
        entity_id: The ID of the owning entity.
        asset_type: The type of asset (icon, overview, preview, etc.).
        filename: Original filename retained for reference and re-processing.
        asset_uri: S3 URI of the converted asset in the assets bucket.
    """

    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, native_enum=False, length=20),
        nullable=False,
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, native_enum=False, length=20),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_uri: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        Index("ix_assets_entity", "entity_type", "entity_id"),
    )
