"""
Unit tests for the Scheduler singleton and JobModel.
"""

from collections.abc import Generator

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.core.exceptions import UnknownTaskError
from src.api.tasks.scheduler import JobModel, Scheduler


def make_scheduler() -> Scheduler:
    """
    Build a Scheduler instance isolated from the process-wide singleton,
    so tests don't collide with the real jobs registered in job_registry.py.
    """
    instance = object.__new__(Scheduler)
    instance.jobs = []
    instance.scheduler = None
    return instance


def make_job(**overrides) -> JobModel:
    """
    Build a JobModel with sane test defaults, override anything via kwargs.
    """
    defaults = {
        "func": lambda: None,
        "trigger_cls": IntervalTrigger,
        "trigger_kwargs": {"seconds": 30},
        "id": "test_job",
        "name": "Test Job",
        "group": "general",
        "enabled": True,
        "executor": "default",
    }
    defaults.update(overrides)
    return JobModel(**defaults)


@pytest.fixture
def live_scheduler() -> Generator[BackgroundScheduler]:
    """
    A real, started APScheduler instance. Started before jobs are added, to
    match how main.py's lifespan calls scheduler.start() before
    schedule_jobs() - APScheduler only computes a job's next_run_time once
    the scheduler is running, otherwise the job just sits pending.
    """
    scheduler = BackgroundScheduler()
    scheduler.start()
    yield scheduler
    scheduler.shutdown(wait=False)


class TestBuildTrigger:
    def test_merges_overrides_over_defaults(self):
        """
        Test that build_trigger merges override kwargs over the job's
        defaults without dropping unset defaults.
        """
        scheduler = make_scheduler()
        job = make_job(trigger_kwargs={"minutes": 10})

        trigger = scheduler.build_trigger(job, {"minutes": 5})

        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval_length == 5 * 60

    def test_no_overrides_uses_job_defaults(self):
        """
        Test that build_trigger falls back to the job's own trigger_kwargs
        when no overrides are given.
        """
        scheduler = make_scheduler()
        job = make_job(trigger_kwargs={"minutes": 10})

        trigger = scheduler.build_trigger(job)

        assert trigger.interval_length == 10 * 60


class TestScheduleJobs:
    def test_enabled_job_is_registered_and_active(self, live_scheduler):
        """
        Test that an enabled job is added to the live scheduler and is not paused.
        """
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="enabled_job", enabled=True))

        scheduler.schedule_jobs(live_scheduler)

        live_job = live_scheduler.get_job("enabled_job")
        assert live_job.next_run_time is not None

    def test_disabled_job_is_registered_but_paused(self, live_scheduler):
        """
        Test that a disabled job is still added to the live scheduler
        (so it can be resumed later) but starts paused.
        """
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="disabled_job", enabled=False))

        scheduler.schedule_jobs(live_scheduler)

        live_job = live_scheduler.get_job("disabled_job")
        assert live_job is not None
        assert live_job.next_run_time is None

    def test_override_enabled_state_wins_over_code_default(self, live_scheduler):
        """
        Test that a stored override's enabled state takes precedence over
        the job's code-defined default.
        """
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="job_a", enabled=True))

        override = type("Override", (), {"enabled": False, "trigger_args": None})()
        scheduler.schedule_jobs(live_scheduler, overrides={"job_a": override})

        assert live_scheduler.get_job("job_a").next_run_time is None

    def test_override_trigger_args_are_applied(self, live_scheduler):
        """
        Test that a stored override's trigger_args are merged over the
        job's default trigger kwargs when scheduling.
        """
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="job_b", trigger_kwargs={"minutes": 10}))

        override = type("Override", (), {"enabled": None, "trigger_args": {"minutes": 2}})()
        scheduler.schedule_jobs(live_scheduler, overrides={"job_b": override})

        live_trigger = live_scheduler.get_job("job_b").trigger
        assert live_trigger.interval_length == 2 * 60


class TestGetJob:
    def test_returns_matching_job(self):
        scheduler = make_scheduler()
        job = make_job(id="found_me")
        scheduler.add_job(job)

        assert scheduler.get_job("found_me") is job

    def test_raises_for_unknown_id(self):
        scheduler = make_scheduler()

        with pytest.raises(UnknownTaskError):
            scheduler.get_job("does_not_exist")


class TestPauseResumeReschedule:
    def test_pause_and_resume_toggle_next_run_time(self, live_scheduler):
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="toggle_me", enabled=True))
        scheduler.schedule_jobs(live_scheduler)

        scheduler.pause("toggle_me")
        assert live_scheduler.get_job("toggle_me").next_run_time is None

        scheduler.resume("toggle_me")
        assert live_scheduler.get_job("toggle_me").next_run_time is not None

    def test_reschedule_keeps_active_job_active(self, live_scheduler):
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="active_job", trigger_kwargs={"minutes": 10}))
        scheduler.schedule_jobs(live_scheduler)

        scheduler.reschedule("active_job", CronTrigger(hour=9))

        live_job = live_scheduler.get_job("active_job")
        assert live_job.next_run_time is not None
        assert isinstance(live_job.trigger, CronTrigger)

    def test_reschedule_keeps_paused_job_paused(self, live_scheduler):
        """
        Test that rescheduling a paused job doesn't silently resume it -
        APScheduler's own reschedule_job() always computes a next run time,
        so Scheduler.reschedule() must re-pause it afterwards.
        """
        scheduler = make_scheduler()
        scheduler.add_job(make_job(id="paused_job", enabled=False, trigger_kwargs={"minutes": 10}))
        scheduler.schedule_jobs(live_scheduler)
        assert live_scheduler.get_job("paused_job").next_run_time is None

        scheduler.reschedule("paused_job", IntervalTrigger(minutes=5))

        live_job = live_scheduler.get_job("paused_job")
        assert live_job.next_run_time is None
        assert live_job.trigger.interval_length == 5 * 60
