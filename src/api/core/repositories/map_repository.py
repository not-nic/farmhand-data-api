"""
Map Repository containing map database interactions.
see: base_repository.py to see the base repository to inherit from.
"""

from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.db.models import Map
from src.api.core.repositories import Repository


class MapRepository(Repository[Map]):
    """
    Map Repository for interaction with the DB
    """

    def __init__(self, db: Session):
        super().__init__(db, Map)

    def get_by_status(self, status: IngestionStatus) -> list[Map]:
        """
        Retrieve a list of maps for a given ingestion status enum, e.g. PENDING, DOWNLOADED.
        :param status: The ingestion status to retrieve.
        :return: (list) A list of maps with a matching status.
        """
        return self.db.query(Map).filter(Map.ingestion_status == status).all()
