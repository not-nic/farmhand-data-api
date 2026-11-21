"""
Module containing unit tests for the '/data/reingest' routes, covering the
optional 'handlers' query parameter and removal of the temporary
'/data/parse-xml' endpoint.
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.api.constants import IngestionStatus, XmlHandler
from src.api.core.config import settings
from src.api.services.maps.map_ingestion_service import MapIngestionService


class TestReingestHandlersFilter:
    """
    Tests for the optional 'handlers' query param on the reingest routes.
    """

    REINGEST_MAP_URL = f"{settings.API_V1_STR}/data/reingest/1"
    REINGEST_ALL_URL = f"{settings.API_V1_STR}/data/reingest"

    def test_reingest_map_with_handlers_and_extracted_stage(self, client: TestClient, mocker, db):
        """
        A single-map reingest with stage=EXTRACTED and a handlers filter
        should be accepted and pass the handlers through to the service.
        """
        mock_reingest_map = mocker.patch.object(MapIngestionService, "reingest_map")

        response = client.post(
            self.REINGEST_MAP_URL,
            params={"stage": IngestionStatus.EXTRACTED.value, "handlers": "vehicles"},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "handlers: vehicles" in response.json()["message"]
        mock_reingest_map.assert_called_once_with(1, IngestionStatus.EXTRACTED, [XmlHandler.VEHICLES])

    def test_reingest_all_maps_with_handlers_and_extracted_stage(
        self, client: TestClient, mocker, db
    ):
        """
        The all-maps reingest with stage=EXTRACTED and a handlers filter
        should be accepted and pass the handlers through to the service.
        """
        mock_reingest_all_maps = mocker.patch.object(MapIngestionService, "reingest_all_maps")

        response = client.post(
            self.REINGEST_ALL_URL,
            params={"stage": IngestionStatus.EXTRACTED.value, "handlers": "vehicles"},
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "handlers: vehicles" in response.json()["message"]
        mock_reingest_all_maps.assert_called_once_with(
            IngestionStatus.EXTRACTED, [XmlHandler.VEHICLES]
        )

    def test_reingest_map_with_handlers_requires_extracted_stage(
        self, client: TestClient, mocker, db
    ):
        """
        Supplying handlers with a stage other than EXTRACTED should be
        rejected with a 400 before the background task is scheduled.
        """
        mock_reingest_map = mocker.patch.object(MapIngestionService, "reingest_map")

        response = client.post(
            self.REINGEST_MAP_URL,
            params={"stage": IngestionStatus.PENDING.value, "handlers": "vehicles"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == (
            "Handlers can only be selected when reingesting from stage 'EXTRACTED'."
        )
        mock_reingest_map.assert_not_called()

    def test_reingest_all_maps_with_handlers_requires_extracted_stage(
        self, client: TestClient, mocker, db
    ):
        """
        Supplying handlers with a stage other than EXTRACTED should be
        rejected with a 400 before the background task is scheduled.
        """
        mock_reingest_all_maps = mocker.patch.object(MapIngestionService, "reingest_all_maps")

        response = client.post(
            self.REINGEST_ALL_URL,
            params={"stage": IngestionStatus.PENDING.value, "handlers": "vehicles"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == (
            "Handlers can only be selected when reingesting from stage 'EXTRACTED'."
        )
        mock_reingest_all_maps.assert_not_called()

    def test_reingest_map_with_unknown_handler_is_rejected(self, client: TestClient, mocker, db):
        """
        An unknown handler value should fail FastAPI's enum validation
        with a 422, before reaching the route body.
        """
        mock_reingest_map = mocker.patch.object(MapIngestionService, "reingest_map")

        response = client.post(
            self.REINGEST_MAP_URL,
            params={"stage": IngestionStatus.EXTRACTED.value, "handlers": "unknown"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_reingest_map.assert_not_called()

    def test_reingest_map_without_handlers_is_unchanged(self, client: TestClient, mocker, db):
        """
        Omitting 'handlers' entirely should preserve existing behaviour and
        call the service with handlers=None.
        """
        mock_reingest_map = mocker.patch.object(MapIngestionService, "reingest_map")

        response = client.post(self.REINGEST_MAP_URL, params={"stage": IngestionStatus.PENDING.value})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "handlers" not in response.json()["message"]
        mock_reingest_map.assert_called_once_with(1, IngestionStatus.PENDING, None)

    def test_reingest_all_maps_without_handlers_is_unchanged(
        self, client: TestClient, mocker, db
    ):
        """
        Omitting 'handlers' entirely should preserve existing behaviour and
        call the service with handlers=None.
        """
        mock_reingest_all_maps = mocker.patch.object(MapIngestionService, "reingest_all_maps")

        response = client.post(self.REINGEST_ALL_URL, params={"stage": IngestionStatus.PENDING.value})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "handlers" not in response.json()["message"]
        mock_reingest_all_maps.assert_called_once_with(IngestionStatus.PENDING, None)


class TestParseXmlRouteRemoved:
    """
    Tests confirming the temporary '/data/parse-xml/{mod_id}' endpoint has
    been removed, in favour of '/data/reingest/{mod_id}?stage=EXTRACTED'.
    """

    PARSE_XML_URL = f"{settings.API_V1_STR}/data/parse-xml/1"

    def test_parse_xml_route_is_gone(self, client: TestClient):
        """
        The route should no longer exist and return a 404.
        """
        response = client.post(self.PARSE_XML_URL)

        assert response.status_code == status.HTTP_404_NOT_FOUND
