"""
Repository for Asset database interactions.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from src.api.constants import AssetType
from src.api.core.db.models.assets import Asset
from src.api.core.repositories.base_repository import Repository


class AssetRepository(Repository[Asset]):
    """
    Repository for Asset database interactions, for both map and vehicle assets.
    """

    def __init__(self, db: Session):
        super().__init__(db, Asset)

    def get_by_map(self, map_id: int) -> list[Asset]:
        """
        Get all assets for a given map.
        :param map_id: The ID of the owning map.
        :return: List of assets belonging to the map.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).all()

    def get_by_map_and_type(self, map_id: int, asset_type: AssetType) -> Asset | None:
        """
        Get a specific asset type of a map.
        :param map_id: The ID of the owning map.
        :param asset_type: The type of asset to look up.
        :return: Asset if it exists, else None.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.map_id == map_id, self.model.asset_type == asset_type)
            .first()
        )

    def get_by_vehicle_and_type(self, vehicle_id: UUID, asset_type: AssetType) -> Asset | None:
        """
        Get a specific asset type of a vehicle.
        :param vehicle_id: The ID of the owning vehicle.
        :param asset_type: The type of asset to look up.
        :return: Asset if it exists, else None.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.vehicle_id == vehicle_id, self.model.asset_type == asset_type)
            .first()
        )

    def get_pending_map_assets(self, limit: int | None = None) -> list[Asset]:
        """
        Get map assets registered but not yet converted and uploaded.
        :param limit: Maximum number of assets to return.
        :return: List of map assets that are not ingested.
        """
        return self._pending(self.model.map_id.is_not(None), limit)

    def get_pending_vehicle_assets(self, limit: int | None = None) -> list[Asset]:
        """
        Get vehicle assets registered but not yet converted and uploaded.
        :param limit: Maximum number of assets to return.
        :return: List of vehicle assets that are not ingested.
        """
        return self._pending(self.model.vehicle_id.is_not(None), limit)

    def mark_ingested(self, asset: Asset) -> Asset:
        """
        Mark an asset as ingested.
        :param asset: (Asset) a given asset to update.
        :return: (Asset) the updated asset.
        """
        return self.update(asset, is_ingested=True)

    def upsert_map_asset(
        self,
        map_id: int,
        asset_type: AssetType,
        filename: str,
        asset_uri: str,
    ) -> Asset:
        """
        Create or update an asset for a given map and asset type.
        :param map_id: The ID of the owning map.
        :param asset_type: The type of asset.
        :param filename: Original filename for reference.
        :param asset_uri: S3 URI of the converted asset.
        :return: Created or updated Asset.
        """
        existing = self.get_by_map_and_type(map_id, asset_type)
        if existing:
            return self.update(existing, filename=filename, asset_uri=asset_uri)
        return self.create(
            map_id=map_id,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
        )

    def upsert_vehicle_asset(
        self,
        vehicle_id: UUID,
        asset_type: AssetType,
        filename: str,
        asset_uri: str,
        is_ingested: bool = False,
        commit: bool = True,
    ) -> Asset:
        """
        Create or update an asset for a vehicle and asset type.
        :param vehicle_id: The ID of the owning vehicle.
        :param asset_type: The type of asset.
        :param filename: Key of the raw .dds in the ingest bucket.
        :param asset_uri: S3 URI of the converted asset in the assets bucket.
        :param is_ingested: If the converted asset is already in the assets bucket.
        :param commit: Commit immediately, if False the row is only flushed.
        :return: The created or updated asset.
        """
        asset = self.get_by_vehicle_and_type(vehicle_id, asset_type)
        if asset:
            asset.filename = filename
            asset.asset_uri = asset_uri
            asset.is_ingested = is_ingested
        else:
            asset = self.model(
                vehicle_id=vehicle_id,
                asset_type=asset_type,
                filename=filename,
                asset_uri=asset_uri,
                is_ingested=is_ingested,
            )
            self.db.add(asset)

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return asset

    def _pending(self, owner_filter, limit: int | None) -> list[Asset]:
        """
        Get assets that are not ingested, for one kind of owner.
        :param owner_filter: SQL filter selecting the owner kind.
        :param limit: Maximum number of assets to return.
        :return: List of assets that are not ingested.
        """
        query = self.db.query(self.model).filter(
            self.model.is_ingested.is_(False), owner_filter
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()
