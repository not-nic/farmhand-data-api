"""
Python module containing tests for the map ingestion service.
"""
from src.api.constants import ModHubLabels
from src.api.core.repositories import MapRepository
from src.api.core.schema.mods import ModPreviewModel
from src.api.services.maps.map_ingestion_service import MapIngestionService
from src.api.services.maps.map_scraping_service import NewMapCandidate
from src.api.services.maps.map_service import MapService


class TestMapIngestionService:
    """
    Tests for the Map Ingestion Service
    """

    async def test_get_new_maps(
            self,
            mocker,
            db,
            mod_detail,
            mock_mod_hub_service,
            mock_s3,
            mock_file_parser_service,
    ):
        """
        Test that the map service gets new maps, uploads them to S3, extracts files,
        and saves them to the database.
        :param mocker: Pytest mocker fixture.
        :param db: Database Session fixture.
        :param mod_detail: Mod detail object fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        :param mock_s3: Fixture for a mocked AWS S3 instance and bucket.
        :param mock_file_parser_service: Fixture containing a mocked file parser service.
        """
        map_service = MapService(db)
        map_ingestion_service = MapIngestionService(db)

        candidates = [
            NewMapCandidate(
                preview=ModPreviewModel(id=123456, name="Custom Map 1", label=ModHubLabels.NEW),
                prefetched_detail=mod_detail.model_copy(
                    update={"id": 123456, "name": "Custom Map 1", "category": "map_europe", "version": "1.0.0.0"}
                ),
            ),
            NewMapCandidate(
                preview=ModPreviewModel(id=456789, name="Custom Map 2", label=ModHubLabels.NEW),
                prefetched_detail=mod_detail.model_copy(
                    update={"id": 456789, "name": "Custom Map 2", "category": "map_europe", "version": "1.0.0.0"}
                ),
            ),
        ]
        mocker.patch.object(
            map_ingestion_service.scraper_service, "check_for_new_maps", new=mocker.AsyncMock(return_value=candidates)
        )

        await map_ingestion_service.get_new_maps()

        # assert two mods were added to the database.
        assert len(map_service.get_maps()) == 2

        # since details were prefetched, scrape_map_details should not re-scrape them.
        mock_mod_hub_service.scrape_mod.assert_not_called()

    async def test_get_new_maps_with_no_new_maps(self, db, mock_mod_hub_service):
        """
        Test get new maps when no new or updated maps are available.
        :param db: Database Session fixture.
        :param mock_mod_hub_service: Fixture containing a mocked instance of the ModHub Service.
        """
        map_ingestion_service = MapIngestionService(db)
        map_ingestion_service.scraper_service.mod_hub_service = mock_mod_hub_service
        await map_ingestion_service.get_new_maps()
        map_repository = MapRepository(db)
        assert len(map_repository.all()) == 0
