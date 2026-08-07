"""
Unit tests for TaskService.
"""

from collections.abc import Generator

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.core.exceptions import InvalidTaskTriggerError, UnknownTaskError
from src.api.core.repositories import TaskRepository
from src.api.core.schema.tasks import TaskUpdateRequest
from src.api.services.tasks.task_service import TaskService
from src.api.tasks.scheduler import JobModel, Scheduler


def make_job(**overrides) -> JobModel:
    """
    Build a JobModel with sane test defaults, override anything via kwargs.
    """
    defaults = {
        "func": lambda: None,
        "trigger_cls": IntervalTrigger,
        "trigger_kwargs": {"minutes": 10},
        "id": "download_pending_maps",
        "name": "Download PENDING maps to S3",
        "group": "pipeline",
        "enabled": True,
        "executor": "default",
    }
    defaults.update(overrides)
    return JobModel(**defaults)


@pytest.fixture
def wired_scheduler() -> Generator[Scheduler]:
    """
    A Scheduler instance isolated from the process-wide singleton, wired to
    a real, started APScheduler with two test jobs: an enabled interval job
    and a disabled cron job.
    """
    scheduler = object.__new__(Scheduler)
    scheduler.jobs = []
    scheduler.scheduler = None

    scheduler.add_job(make_job())
    scheduler.add_job(
        make_job(
            id="get_new_maps",
            name="Scrape ModHub for new Farming Simulator maps",
            group="discovery",
            trigger_cls=CronTrigger,
            trigger_kwargs={"hour": 14, "minute": 30},
            enabled=False,
        )
    )

    live_scheduler = BackgroundScheduler()
    live_scheduler.start()
    scheduler.schedule_jobs(live_scheduler)

    yield scheduler

    live_scheduler.shutdown(wait=False)


@pytest.fixture
def task_service(db, wired_scheduler) -> TaskService:
    return TaskService(db, scheduler=wired_scheduler)


class TestListTasks:
    def test_lists_every_registered_job(self, task_service):
        statuses = task_service.list_tasks()
        assert {s.id for s in statuses} == {"download_pending_maps", "get_new_maps"}

    def test_resolves_code_defaults_when_no_override_exists(self, task_service):
        statuses = {s.id: s for s in task_service.list_tasks()}

        download = statuses["download_pending_maps"]
        assert download.enabled is True
        assert download.paused is False
        assert download.trigger_type == "interval"
        assert download.trigger_args == {"minutes": 10}

        discovery = statuses["get_new_maps"]
        assert discovery.enabled is False
        assert discovery.paused is True
        assert discovery.trigger_type == "cron"


class TestGetTask:
    def test_raises_for_unknown_job_id(self, task_service):
        with pytest.raises(UnknownTaskError):
            task_service.get_task("does_not_exist")


class TestUpdateTask:
    def test_disabling_a_job_pauses_it_live(self, task_service):
        status = task_service.update_task("download_pending_maps", TaskUpdateRequest(enabled=False))

        assert status.enabled is False
        assert status.paused is True

    def test_disabling_a_job_persists_an_override(self, db, task_service):
        task_service.update_task("download_pending_maps", TaskUpdateRequest(enabled=False))

        stored = TaskRepository(db).get_by_job_id("download_pending_maps")
        assert stored is not None
        assert stored.enabled is False

    def test_enabling_a_paused_job_resumes_it_live(self, task_service):
        status = task_service.update_task("get_new_maps", TaskUpdateRequest(enabled=True))

        assert status.enabled is True
        assert status.paused is False

    def test_trigger_args_merge_over_current_effective_args(self, task_service):
        status = task_service.update_task(
            "download_pending_maps", TaskUpdateRequest(trigger_args={"minutes": 5})
        )

        assert status.trigger_args == {"minutes": 5}

    def test_trigger_args_are_applied_live(self, task_service, wired_scheduler):
        task_service.update_task(
            "download_pending_maps", TaskUpdateRequest(trigger_args={"minutes": 5})
        )

        live_trigger = wired_scheduler.get_live_job("download_pending_maps").trigger
        assert live_trigger.interval_length == 5 * 60

    def test_trigger_change_does_not_resume_a_disabled_job(self, task_service):
        """
        A trigger-only update on a disabled job must not silently re-enable it.
        """
        status = task_service.update_task(
            "get_new_maps", TaskUpdateRequest(trigger_args={"hour": 9})
        )

        assert status.enabled is False
        assert status.paused is True

    def test_invalid_trigger_args_raise_without_persisting(self, db, task_service):
        with pytest.raises(InvalidTaskTriggerError):
            task_service.update_task(
                "download_pending_maps",
                TaskUpdateRequest(trigger_args={"not_a_real_trigger_kwarg": 1}),
            )

        assert TaskRepository(db).get_by_job_id("download_pending_maps") is None

    def test_unknown_job_id_raises(self, task_service):
        with pytest.raises(UnknownTaskError):
            task_service.update_task("does_not_exist", TaskUpdateRequest(enabled=False))


class TestResetTask:
    def test_removes_stored_override(self, db, task_service):
        task_service.update_task("download_pending_maps", TaskUpdateRequest(enabled=False))
        assert TaskRepository(db).get_by_job_id("download_pending_maps") is not None

        task_service.reset_task("download_pending_maps")

        assert TaskRepository(db).get_by_job_id("download_pending_maps") is None

    def test_reapplies_code_default_live(self, task_service):
        task_service.update_task(
            "download_pending_maps", TaskUpdateRequest(enabled=False, trigger_args={"minutes": 5})
        )

        status = task_service.reset_task("download_pending_maps")

        assert status.enabled is True
        assert status.trigger_args == {"minutes": 10}
