"""
Mod Description Repository containing database interactions.
see: base_repository.py to see the base repository to inherit from.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.mods import ModDescription
from src.api.core.repositories import Repository


class ModDescriptionRepository(Repository[ModDescription]):
    """
    Repository for ModDescription database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, ModDescription)

    def get_by_map_id(self, map_id: int) -> ModDescription | None:
        """
        Get the ModDescription for a given map ID.
        :param map_id: The map ID to look up.
        :return: ModDescription if it exists, else None.
        """
        return self.db.query(self.model).filter(self.model.map_id == map_id).first()

    def upsert(self, map_id: int, **kwargs) -> ModDescription:
        """
        Upsert a mod description with new or updated data.
        :param map_id: (int) a given map to update.
        :param kwargs: Additional arguments for the ModDescription model.
        :return: A created or updated ModDescription model.
        """
        existing = self.get_by_map_id(map_id)
        if existing:
            return self.update(existing, **kwargs)
        return self.create(map_id=map_id, **kwargs)
