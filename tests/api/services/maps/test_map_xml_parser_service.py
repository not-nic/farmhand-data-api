"""
Python module containing tests for the Map XML Parser Service's selective
handler support used by a handler-scoped reingest.
"""
from botocore.exceptions import ClientError

from src.api.constants import IngestionStatus, XmlHandler
from src.api.core.schema.maps import MapModel
from src.api.services.maps.map_service import MapService
from src.api.services.maps.map_xml_parser_service import MapXmlParserService


def _make_extracted_map(db, mod_detail):
    """
    Create a map in the database and advance it to 'EXTRACTED', as it
    would be once its files are in S3.
    """
    map_service = MapService(db)
    map_obj = map_service.create_map(MapModel(**mod_detail.model_dump()))
    map_obj = map_service.update_map(map_obj, ingestion_status=IngestionStatus.EXTRACTED)
    return map_obj, map_service


class TestMapXmlParserServiceHandlerSelection:
    """
    Tests for MapXmlParserService.parse_map's optional `handlers` filter.
    """

    def test_parse_map_with_handlers_runs_only_the_selected_handler(self, db, mod_detail, mocker):
        """
        Only the handler whose key is in `handlers` should run.
        """
        map_obj, map_service = _make_extracted_map(db, mod_detail)
        xml_parser_service = MapXmlParserService(db, map_service=map_service)

        mocks = {
            handler.key: mocker.patch.object(handler, "process")
            for handler in xml_parser_service.handlers
        }

        xml_parser_service.parse_map(map_obj, handlers={XmlHandler.VEHICLES})

        mocks[XmlHandler.VEHICLES].assert_called_once_with(map_obj)
        for key, mock in mocks.items():
            if key != XmlHandler.VEHICLES:
                mock.assert_not_called()

    def test_parse_map_with_handlers_leaves_ingestion_status_untouched(self, db, mod_detail, mocker):
        """
        A selective reparse must not mark a healthy map FAILED or flip it
        to PARSED — it only touches whatever the selected handler stores.
        """
        map_obj, map_service = _make_extracted_map(db, mod_detail)
        xml_parser_service = MapXmlParserService(db, map_service=map_service)

        for handler in xml_parser_service.handlers:
            mocker.patch.object(handler, "process")

        xml_parser_service.parse_map(map_obj, handlers={XmlHandler.VEHICLES})

        refreshed = map_service.get_map_by_id(map_obj.id)
        assert refreshed.ingestion_status == IngestionStatus.EXTRACTED
        assert refreshed.ingestion_error is None

    def test_parse_map_with_handlers_does_not_fail_map_on_client_error(self, db, mod_detail, mocker):
        """
        An S3 failure within a selected handler is logged, not persisted
        onto the map's ingestion status.
        """
        map_obj, map_service = _make_extracted_map(db, mod_detail)
        xml_parser_service = MapXmlParserService(db, map_service=map_service)

        for handler in xml_parser_service.handlers:
            mock = mocker.patch.object(handler, "process")
            if handler.key == XmlHandler.VEHICLES:
                mock.side_effect = ClientError({"Error": {"Code": "500", "Message": "boom"}}, "GetObject")

        xml_parser_service.parse_map(map_obj, handlers={XmlHandler.VEHICLES})

        refreshed = map_service.get_map_by_id(map_obj.id)
        assert refreshed.ingestion_status == IngestionStatus.EXTRACTED
        assert refreshed.ingestion_error is None

    def test_parse_map_with_handlers_does_not_fail_map_on_parse_error(self, db, mod_detail, mocker):
        """
        An XML parse failure within a selected handler is logged, not
        persisted onto the map's ingestion status.
        """
        from xml.etree.ElementTree import ParseError

        map_obj, map_service = _make_extracted_map(db, mod_detail)
        xml_parser_service = MapXmlParserService(db, map_service=map_service)

        for handler in xml_parser_service.handlers:
            mock = mocker.patch.object(handler, "process")
            if handler.key == XmlHandler.VEHICLES:
                mock.side_effect = ParseError("malformed xml")

        xml_parser_service.parse_map(map_obj, handlers={XmlHandler.VEHICLES})

        refreshed = map_service.get_map_by_id(map_obj.id)
        assert refreshed.ingestion_status == IngestionStatus.EXTRACTED
        assert refreshed.ingestion_error is None

    def test_parse_map_without_handlers_runs_all_and_updates_status(self, db, mod_detail, mocker):
        """
        Unchanged behaviour: with no `handlers` filter every handler runs
        and the ingestion result is written as before.
        """
        map_obj, map_service = _make_extracted_map(db, mod_detail)
        xml_parser_service = MapXmlParserService(db, map_service=map_service)

        mocks = [mocker.patch.object(handler, "process") for handler in xml_parser_service.handlers]

        xml_parser_service.parse_map(map_obj)

        for mock in mocks:
            mock.assert_called_once_with(map_obj)

        refreshed = map_service.get_map_by_id(map_obj.id)
        assert refreshed.ingestion_status == IngestionStatus.PARSED
        assert refreshed.ingestion_error is None
