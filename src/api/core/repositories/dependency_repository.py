"""
Python module containing a Repository for dependencies.
"""

from sqlalchemy.orm import Session

from src.api.core.db.models.mods import Dependency
from src.api.core.repositories import Repository


class DependencyRepository(Repository[Dependency]):
    """
    Repository for Dependency database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, Dependency)

    def get_by_mod_id(self, mod_id: str) -> Dependency | None:
        """
        Get a Dependency by its mod_id string.
        :param mod_id: The mod identifier e.g. 'FS25_John_Deere_Workshop'.
        :return: Dependency if it exists, else None.
        """
        return self.db.query(self.model).filter(self.model.mod_id == mod_id).first()

    def upsert(self, mod_id: str) -> Dependency:
        """
        Get an existing dependency by its mod_id or create it if it doesn't exist.
        :param mod_id: The mod identifier e.g. 'FS25_John_Deere_Workshop'.
        :return: Existing or newly created Dependency.
        """
        existing = self.get_by_mod_id(mod_id)
        if existing:
            return existing
        return self.create(mod_id=mod_id)
