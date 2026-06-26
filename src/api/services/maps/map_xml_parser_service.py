"""
Map XML Parser Service Module used for parsing a map's extracted XML
files into structured metadata and persisting it onto the Map record.

This is intentionally a skeleton — fill in _parse_map_xml with the
actual field extraction once you've decided what the XML should drive
on the Map model (e.g. map name, terrain size, preview image path).
"""
from sqlalchemy.orm import Session

from src.api.services.aws_service import AwsService
from src.api.services.maps.map_service import MapService


class MapXmlParserService:
    def __init__(
            self,
            db: Session,
            map_service: MapService | None = None,
            aws_service: AwsService | None = None,
    ):
        self.map_service = map_service or MapService(db)
        self.aws_service = aws_service or AwsService()

    def parse_and_update(self) -> None:
        """
        """
        raise NotImplementedError("Not Implemented Yet.")

    def _parse_map_xml(self) -> dict:
        """
        """
        raise NotImplementedError("XML parsing logic not yet implemented")
