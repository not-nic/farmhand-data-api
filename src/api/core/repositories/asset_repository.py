"""
Repository for Asset database interactions.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType, EntityType
from src.api.core.db.models.assets import Asset
from src.api.core.repositories import Repository


class AssetRepository(Repository[Asset]):
    """
    Repository for Asset database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, Asset)

    def get_by_entity(self, entity_type: EntityType, entity_id: int) -> list[Asset]:
        """
        Get all assets for a given entity.
        :param entity_type: The type of entity.
        :param entity_id: The ID of the owning entity.
        :return: List of assets belonging to the entity.
        """
        return (
            self.db.query(self.model)
            .filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,
            )
            .all()
        )

    def get_by_entity_and_type(
        self,
        entity_type: EntityType,
        entity_id: int,
        asset_type: AssetType,
    ) -> Asset | None:
        """
        Get a specific asset type for a given entity.
        Useful for checking if an icon or overview already exists.
        :param entity_type: The type of entity.
        :param entity_id: The ID of the owning entity.
        :param asset_type: The type of asset to look up.
        :return: Asset if it exists, else None.
        """
        return (
            self.db.query(self.model)
            .filter(
                self.model.entity_type == entity_type,
                self.model.entity_id == entity_id,
                self.model.asset_type == asset_type,
            )
            .first()
        )

    def upsert(
        self,
        entity_type: EntityType,
        entity_id: int,
        asset_type: AssetType,
        filename: str,
        asset_uri: str,
    ) -> Asset:
        """
        Create or update an asset for a given entity and asset type.
        :param entity_type: The type of entity.
        :param entity_id: The ID of the owning entity.
        :param asset_type: The type of asset.
        :param filename: Original filename for reference.
        :param asset_uri: S3 URI of the converted asset.
        :return: Created or updated Asset.
        """
        existing = self.get_by_entity_and_type(entity_type, entity_id, asset_type)
        if existing:
            return self.update(existing, filename=filename, asset_uri=asset_uri)
        return self.create(
            entity_type=entity_type,
            entity_id=entity_id,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
        )
