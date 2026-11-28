"""
SQLAlchemy model for a farmhand Asset.
"""

from typing import TYPE_CHECKING
from uuid import uuid7

from sqlalchemy import (
    UUID,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.api.constants import AssetType
from src.api.core.db.models._model_base import SqlAlchemyBase

if TYPE_CHECKING:
    from src.api.core.db.models.maps import Map
    from src.api.core.db.models.vehicles import Vehicle


class Asset(SqlAlchemyBase):
    """
    Model of farmhand asset and their asset locations. An asset is owned by
    exactly one of a map or a vehicle.

    Attributes:
        id: primary key.
        map_id: The owning map, or None when owned by a vehicle.
        vehicle_id: The owning vehicle, or None when owned by a map.
        asset_type: The type of asset (icon, overview, preview, etc.).
        filename: Original filename retained for reference and re-processing.
        asset_uri: S3 URI of the converted asset in the assets bucket.
        is_ingested: (bool) if the asset has been ingested and available to the assets bucket.
    """

    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    map_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("maps.id", ondelete="CASCADE"), nullable=True, index=True
    )
    vehicle_id: Mapped[UUID | None] = mapped_column(
        UUID, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, native_enum=False, length=20),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    is_ingested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    map: Mapped[Map | None] = relationship("Map", back_populates="assets")
    vehicle: Mapped[Vehicle | None] = relationship("Vehicle", back_populates="assets")

    __table_args__ = (
        CheckConstraint(
            "(map_id IS NULL) <> (vehicle_id IS NULL)", name="ck_assets_single_owner"
        ),
        UniqueConstraint("map_id", "asset_type", name="uq_assets_map_asset_type"),
        UniqueConstraint("vehicle_id", "asset_type", name="uq_assets_vehicle_asset_type"),
    )
