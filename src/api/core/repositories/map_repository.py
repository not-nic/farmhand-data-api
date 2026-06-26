"""
Map Repository containing map database interactions.
see: base_repository.py to see the base repository to inherit from.
"""
from datetime import datetime

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
        return self.db.query(self.model).filter(self.model.ingestion_status == status).all()

    def get_with_data_uri(self) -> list[Map]:
        """
        Get all maps that currently have a data_uri.
        :return: (list) of maps with a valid data_uri.
        """
        return self.db.query(self.model).filter(self.model.data_uri.isnot(None)).all()

    def get_stalled(self, ingestion_status: IngestionStatus, stalled_before: datetime) -> list[Map]:
        """
        Get all maps that are stalled for a given ingest_status, and stalled 'threshold'
        :param ingestion_status: (IngestionStatus) The ingestion stage.
        :param stalled_before: (datetime) a datetime value to decide what's 'stalled'.
        :return: (list) A list of maps that are in a stalled state.
        """
        return self.db.query(self.model).filter(
            self.model.ingestion_status == ingestion_status,
            self.model.ingestion_updated_at < stalled_before
        ).all()
