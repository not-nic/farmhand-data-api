"""
Python module containing tests for the MapRecoveryService.
"""
from datetime import UTC, datetime, timedelta

import pytest

from src.api.constants import IngestionStatus
from src.api.core.schema.maps import MapModel
from src.api.services.maps.map_service import MapService
from src.api.services.maps.recovery.map_recovery_service import MapRecoveryService


class TestReprocessStalledDownloads:
    """
    Tests for MapRecoveryService.retry_stalled_downloads.
    """

    @pytest.fixture
    def map_service(self, db) -> MapService:
        """
        Fixture of the MapService.
        :param db: (Fixture) the database session fixture/
        :return: An instance of the MapService.
        """
        return MapService(db)

    @pytest.fixture
    def map_recovery_service(self, db) -> MapRecoveryService:
        """
        Fixture for the map recovery service.
        :param db: (Fixture) the database session fixture.
        :return: An instance of the MapRecoveryService
        """
        return MapRecoveryService(db)

    @pytest.fixture
    def map_model(self, mod_detail) -> MapModel:
        """Fixture for a valid MapModel built from the shared mod_detail fixture."""
        return MapModel(**mod_detail.model_dump())

    @pytest.fixture
    def stalled_map(self, map_service, map_model):
        """
        Fixture for a map stuck at DOWNLOADING with an
        ingestion_updated_at beyond the stall threshold.
        """
        map_obj = map_service.create_map(map_model)
        return map_service.update_map(
            map_obj,
            ingestion_status=IngestionStatus.DOWNLOADING,
            ingestion_updated_at=datetime.now() - timedelta(hours=2),
        )

    @pytest.fixture
    async def active_downloading_map(self, map_service, map_model):
        """
        Fixture for a map 'DOWNLOADING' that updated recently and is not stalled.
        """
        map_obj = map_service.create_map(map_model)
        return map_service.update_map(
            map_obj,
            ingestion_status=IngestionStatus.DOWNLOADING,
            ingestion_updated_at=datetime.now() - timedelta(minutes=2),
        )

    async def test_resets_stalled_map_to_pending(
        self, map_service, map_recovery_service, stalled_map
    ):
        """
        Test that a map stuck at DOWNLOADING beyond the threshold is reset to PENDING.
        """
        await map_recovery_service.retry_stalled_downloads()

        updated = map_service.get_map_by_id(stalled_map.id)
        assert updated.ingestion_status == IngestionStatus.PENDING

    async def test_records_error_message_on_reset(
        self, map_service, map_recovery_service, stalled_map
    ):
        """
        Test that a stalled map has an ingestion_error when reset.
        """
        await map_recovery_service.retry_stalled_downloads()

        updated = map_service.get_map_by_id(stalled_map.id)
        assert updated.ingestion_error is not None
        assert "DOWNLOADING" in updated.ingestion_error

    async def test_does_not_reset_active_downloading_map(
        self, map_service, map_recovery_service, active_downloading_map
    ):
        """
        test that a map currently 'DOWNLOADING' is left in progress and is
        not reset.
        """
        await map_recovery_service.retry_stalled_downloads()

        updated = map_service.get_map_by_id(active_downloading_map.id)
        assert updated.ingestion_status == IngestionStatus.DOWNLOADING

    @pytest.mark.parametrize("status", [
        IngestionStatus.PENDING,
        IngestionStatus.DOWNLOADED,
        IngestionStatus.EXTRACTING,
        IngestionStatus.EXTRACTED,
        IngestionStatus.FAILED,
    ])
    async def test_does_not_affect_maps_in_other_statuses(
        self, map_service, map_recovery_service, map_model, status
    ):
        """
        Test that maps with status other than downloading are ignored
        by the re-process of a stalled map.
        """
        map_obj = map_service.create_map(map_model)
        map_service.update_map(
            map_obj,
            ingestion_status=status,
            ingestion_updated_at=datetime.now(UTC) - timedelta(hours=2),
        )

        await map_recovery_service.retry_stalled_downloads()

        updated = map_service.get_map_by_id(map_obj.id)
        assert updated.ingestion_status == status

    async def test_no_stalled_maps_does_nothing(self, map_service, map_recovery_service):
        """
        test that when there are no stalled maps, nothing is returned.
        """
        await map_recovery_service.retry_stalled_downloads()
        assert map_service.get_maps() == []
