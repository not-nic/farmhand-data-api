"""
Python module containing tests for the map ingestion service.
"""
import pytest

from src.api.constants import IngestionStatus, ModHubLabels, XmlHandler
from src.api.core.repositories import MapRepository
from src.api.core.repositories.farmland_repository import FarmlandRepository
from src.api.core.repositories.info_layer_repository import InfoLayerRepository
from src.api.core.schema.maps import MapModel
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

    def test_reingest_map_with_handlers_and_non_extracted_stage_raises(self, db):
        """
        Handlers are only meaningful against the 'EXTRACTED' XML-parse stage,
        so selecting them with any other stage must be rejected.
        :param db: Database Session fixture.
        """
        map_ingestion_service = MapIngestionService(db)

        with pytest.raises(ValueError, match="Handlers can only be selected"):
            map_ingestion_service.reingest_map(
                123456, IngestionStatus.PENDING, handlers={XmlHandler.VEHICLES}
            )

    def test_reingest_all_maps_with_handlers_and_non_extracted_stage_raises(self, db):
        """
        Same restriction as reingest_map, for the bulk variant.
        :param db: Database Session fixture.
        """
        map_ingestion_service = MapIngestionService(db)

        with pytest.raises(ValueError, match="Handlers can only be selected"):
            map_ingestion_service.reingest_all_maps(
                IngestionStatus.PARSED, handlers={XmlHandler.VEHICLES}
            )


class TestResetDownstreamIngestion:
    """
    Tests for MapIngestionService._reset_downstream_ingestion's optional
    `handlers` filter, which scopes the reset to only the info layers or
    farmlands owned by a selected handler.
    """

    @staticmethod
    def _make_map_with_downstream_state(db, mod_detail):
        map_service = MapService(db)
        map_obj = map_service.create_map(MapModel(**mod_detail.model_dump()))

        info_layer = InfoLayerRepository(db).create(
            map_id=map_obj.id,
            layer_key="farmlands",
            is_ingested=True,
            asset_uri="s3://bucket/farmlands.json",
        )
        farmland = FarmlandRepository(db).create(
            map_id=map_obj.id,
            info_layer_id=info_layer.id,
            number=1,
            coordinates=[[0, 0], [1, 1]],
            size_ha=12.5,
            area_types=["Open Land"],
        )
        return map_obj, info_layer, farmland

    def test_reset_with_vehicles_handler_resets_neither(self, db, mod_detail):
        """
        Selecting only the vehicles handler must not touch info layers
        or farmlands — vehicles.xml has nothing to do with either.
        """
        map_ingestion_service = MapIngestionService(db)
        map_obj, info_layer, farmland = self._make_map_with_downstream_state(db, mod_detail)

        map_ingestion_service._reset_downstream_ingestion(map_obj, handlers={XmlHandler.VEHICLES})

        refreshed_info_layer = InfoLayerRepository(db).get_by_id(info_layer.id)
        refreshed_farmland = FarmlandRepository(db).get_by_id(farmland.id)

        assert refreshed_info_layer.is_ingested is True
        assert refreshed_info_layer.asset_uri == "s3://bucket/farmlands.json"
        assert refreshed_farmland.coordinates == [[0, 0], [1, 1]]
        assert refreshed_farmland.size_ha == 12.5
        assert refreshed_farmland.area_types == ["Open Land"]

    def test_reset_with_farmlands_handler_resets_only_farmlands(self, db, mod_detail):
        """
        Selecting only the farmlands handler resets farmlands but leaves
        info layers alone.
        """
        map_ingestion_service = MapIngestionService(db)
        map_obj, info_layer, farmland = self._make_map_with_downstream_state(db, mod_detail)

        map_ingestion_service._reset_downstream_ingestion(map_obj, handlers={XmlHandler.FARMLANDS})

        refreshed_info_layer = InfoLayerRepository(db).get_by_id(info_layer.id)
        refreshed_farmland = FarmlandRepository(db).get_by_id(farmland.id)

        assert refreshed_info_layer.is_ingested is True
        assert refreshed_info_layer.asset_uri == "s3://bucket/farmlands.json"
        assert refreshed_farmland.coordinates is None
        assert refreshed_farmland.size_ha is None
        assert refreshed_farmland.area_types is None

    def test_reset_with_info_layers_handler_resets_only_info_layers(self, db, mod_detail):
        """
        Selecting only the info_layers handler resets info layers but
        leaves farmlands alone.
        """
        map_ingestion_service = MapIngestionService(db)
        map_obj, info_layer, farmland = self._make_map_with_downstream_state(db, mod_detail)

        map_ingestion_service._reset_downstream_ingestion(map_obj, handlers={XmlHandler.INFO_LAYERS})

        refreshed_info_layer = InfoLayerRepository(db).get_by_id(info_layer.id)
        refreshed_farmland = FarmlandRepository(db).get_by_id(farmland.id)

        assert refreshed_info_layer.is_ingested is False
        assert refreshed_info_layer.asset_uri is None
        assert refreshed_farmland.coordinates == [[0, 0], [1, 1]]
        assert refreshed_farmland.size_ha == 12.5
        assert refreshed_farmland.area_types == ["Open Land"]

    def test_reset_with_no_handlers_resets_both(self, db, mod_detail):
        """
        Unchanged behaviour: omitting `handlers` resets both info layers
        and farmlands.
        """
        map_ingestion_service = MapIngestionService(db)
        map_obj, info_layer, farmland = self._make_map_with_downstream_state(db, mod_detail)

        map_ingestion_service._reset_downstream_ingestion(map_obj)

        refreshed_info_layer = InfoLayerRepository(db).get_by_id(info_layer.id)
        refreshed_farmland = FarmlandRepository(db).get_by_id(farmland.id)

        assert refreshed_info_layer.is_ingested is False
        assert refreshed_info_layer.asset_uri is None
        assert refreshed_farmland.coordinates is None
        assert refreshed_farmland.size_ha is None
        assert refreshed_farmland.area_types is None


class TestReingestAllMapsWithHandlers:
    """
    Tests for MapIngestionService.reingest_all_maps's optional `handlers`
    filter, which processes maps directly instead of resetting a status
    for the scheduler to pick up.
    """

    @staticmethod
    def _make_map(db, mod_detail, *, map_id: int, name: str, data_uri: str | None):
        map_service = MapService(db)
        map_obj = map_service.create_map(
            MapModel(
                **mod_detail.model_copy(update={"id": map_id, "name": name}).model_dump()
            )
        )
        return map_service.update_map(
            map_obj, ingestion_status=IngestionStatus.EXTRACTED, data_uri=data_uri
        )

    def test_reingest_all_maps_with_handlers_runs_parse_map_per_map_with_data_uri(
            self, db, mod_detail, mocker
    ):
        """
        Only maps with a data_uri are reprocessed, each via parse_map with
        the given handlers, and their statuses are left untouched.
        """
        map_with_data = self._make_map(
            db, mod_detail, map_id=111, name="Map With Data", data_uri="s3://bucket/111/data"
        )
        map_without_data = self._make_map(
            db, mod_detail, map_id=222, name="Map Without Data", data_uri=None
        )

        map_ingestion_service = MapIngestionService(db)
        parse_map_mock = mocker.patch.object(map_ingestion_service.xml_parser_service, "parse_map")
        reset_mock = mocker.patch.object(map_ingestion_service, "_reset_downstream_ingestion")

        map_ingestion_service.reingest_all_maps(
            IngestionStatus.EXTRACTED, handlers={XmlHandler.VEHICLES}
        )

        parse_map_mock.assert_called_once_with(map_with_data, {XmlHandler.VEHICLES})
        reset_mock.assert_called_once_with(map_with_data, {XmlHandler.VEHICLES})

        map_service = MapService(db)
        refreshed_with_data = map_service.get_map_by_id(map_with_data.id)
        refreshed_without_data = map_service.get_map_by_id(map_without_data.id)
        assert refreshed_with_data.ingestion_status == IngestionStatus.EXTRACTED
        assert refreshed_without_data.ingestion_status == IngestionStatus.EXTRACTED

    def test_reingest_all_maps_with_handlers_continues_past_a_failing_map(
            self, db, mod_detail, mocker
    ):
        """
        One map raising while being reprocessed must not stop the rest
        from being processed.
        """
        failing_map = self._make_map(
            db, mod_detail, map_id=111, name="Failing Map", data_uri="s3://bucket/111/data"
        )
        healthy_map = self._make_map(
            db, mod_detail, map_id=222, name="Healthy Map", data_uri="s3://bucket/222/data"
        )

        map_ingestion_service = MapIngestionService(db)

        def _parse_map(map_obj, handlers):
            if map_obj.id == failing_map.id:
                raise RuntimeError("boom")

        parse_map_mock = mocker.patch.object(
            map_ingestion_service.xml_parser_service, "parse_map", side_effect=_parse_map
        )
        reset_mock = mocker.patch.object(map_ingestion_service, "_reset_downstream_ingestion")

        map_ingestion_service.reingest_all_maps(
            IngestionStatus.EXTRACTED, handlers={XmlHandler.VEHICLES}
        )

        assert parse_map_mock.call_count == 2
        # the failing map's exception must not have prevented the reset/
        # processing of the healthy map that follows it.
        reset_mock.assert_called_once_with(healthy_map, {XmlHandler.VEHICLES})
