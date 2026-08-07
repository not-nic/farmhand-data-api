"""
Integration tests for the /tasks API routes.
"""

from collections.abc import Generator

import pytest
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import status

from src.api.tasks import base_scheduler


@pytest.fixture
def wired_base_scheduler(db) -> Generator[None]:
    """
    Wire the real base_scheduler singleton (and its production job
    definitions from job_registry.py) to a disposable, started
    APScheduler instance so the /tasks routes have live state to read and
    mutate. main.py's own lifespan never runs here - Starlette's
    TestClient only sends lifespan events when used as a context manager,
    which the shared `client` fixture does not do.
    """
    live = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(2), "downloads": ThreadPoolExecutor(2)}
    )
    live.start()
    base_scheduler.schedule_jobs(live)
    yield
    live.shutdown(wait=False)


@pytest.mark.usefixtures("wired_base_scheduler")
class TestListAndGetTasks:
    def test_list_tasks_includes_registered_jobs(self, client):
        response = client.get("/api/v1/tasks/")

        assert response.status_code == status.HTTP_200_OK
        ids = {task["id"] for task in response.json()}
        assert "download_pending_maps" in ids
        assert "get_new_maps" in ids

    def test_get_unknown_task_returns_404(self, client):
        response = client.get("/api/v1/tasks/does_not_exist")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("wired_base_scheduler")
class TestUpdateTask:
    def test_invalid_trigger_args_returns_422(self, client):
        response = client.patch(
            "/api/v1/tasks/download_pending_maps",
            json={"trigger_args": {"not_a_real_trigger_kwarg": 1}},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_unknown_task_returns_404(self, client):
        response = client.patch("/api/v1/tasks/does_not_exist", json={"enabled": False})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_disable_then_reset_round_trip(self, client):
        disabled = client.patch("/api/v1/tasks/download_pending_maps", json={"enabled": False})
        assert disabled.status_code == status.HTTP_200_OK
        assert disabled.json()["enabled"] is False
        assert disabled.json()["paused"] is True

        reset = client.delete("/api/v1/tasks/download_pending_maps/reset")
        assert reset.status_code == status.HTTP_200_OK
        assert reset.json()["enabled"] is True
