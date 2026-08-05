"""
Module containing a singleton utility for scheduling jobs with APScheduler.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.base import BaseTrigger

from src.api.core.exceptions import UnknownTaskError
from src.api.core.logger import logger


@dataclass
class JobModel:
    """
    Dataclass for a scheduled background job.

    Attributes:
        func: The function to call when the job fires.
        trigger_cls: The APScheduler trigger class defining when the job runs,
            e.g. IntervalTrigger or CronTrigger.
        trigger_kwargs: Default constructor kwargs for trigger_cls, e.g.
            {"minutes": 10, "start_date": ...}. Kept separate from the built
            trigger so a task override can be merged over them at schedule time.
        id: Unique job identifier.
        name: Human-readable job name to be shown in logs.
        group: A group for the job.
        enabled: Set too False to skip registration without removing the job definition.
        args: Positional arguments passed to func.
        kwargs: Keyword arguments passed to func.
        replace_existing: Replace an existing job with the same id on scheduler start.
    """

    func: Callable[..., Any]
    trigger_cls: type[BaseTrigger]
    trigger_kwargs: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    name: str | None = None
    group: str = "general"
    enabled: bool = True
    args: list | None = None
    kwargs: dict | None = None
    replace_existing: bool = True
    executor: str = "default"


class Scheduler:
    """
    Singleton Scheduler class for scheduling all jobs defined in
    job_registry.py on FastAPI application startup, and for applying
    runtime overrides (enable/disable, trigger changes) requested through
    the /tasks API afterwards.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.jobs = []
                    cls._instance.scheduler = None
        return cls._instance

    def add_job(self, job: JobModel) -> None:
        """
        Add a job to the scheduler registry.
        :param job: The JobModel to register.
        """
        self.jobs.append(job)

    def get_job(self, job_id: str) -> JobModel:
        """
        Get a registered JobModel by its id.
        :param job_id: The job id to look up.
        :return: The matching JobModel.
        :raises UnknownTaskError: if no job with that id is registered.
        """
        for job in self.jobs:
            if job.id == job_id:
                return job
        raise UnknownTaskError(f"No scheduled task found with id '{job_id}'")

    def build_trigger(self, job: JobModel, overrides: dict[str, Any] | None = None) -> BaseTrigger:
        """
        Build a job's trigger, merging any override kwargs over its code-defined
        defaults. Does not change the trigger's type, only its constructor args.
        :param job: The JobModel to build a trigger for.
        :param overrides: kwargs to merge over job.trigger_kwargs, if any.
        :return: A new trigger instance.
        """
        merged = {**job.trigger_kwargs, **(overrides or {})}
        return job.trigger_cls(**merged)

    def schedule_jobs(
        self, scheduler: BaseScheduler, overrides: dict[str, Any] | None = None
    ) -> None:
        """
        Register every job with the APScheduler instance and log a grouped
        summary of what was scheduled and what was skipped. Every job is
        added regardless of its resolved enabled state - a disabled job is
        added then immediately paused, rather than never registered, so it
        can be resumed later through the /tasks API without an app restart.
        :param scheduler: The APScheduler instance.
        :param overrides: A dict of job_id -> Task, applied over the
            code-defined defaults for enabled state and trigger kwargs.
        """
        self.scheduler = scheduler
        overrides = overrides or {}

        enabled_jobs: list[JobModel] = []
        disabled_jobs: list[JobModel] = []

        for job in self.jobs:
            override = overrides.get(job.id)
            enabled = (
                job.enabled if override is None or override.enabled is None else override.enabled
            )
            trigger_args = override.trigger_args if override and override.trigger_args else None

            scheduler.add_job(
                func=job.func,
                trigger=self.build_trigger(job, trigger_args),
                id=job.id,
                name=job.name,
                args=job.args,
                kwargs=job.kwargs,
                replace_existing=job.replace_existing,
                executor=job.executor,
            )

            if enabled:
                enabled_jobs.append(job)
            else:
                scheduler.pause_job(job.id)
                disabled_jobs.append(job)

        groups = sorted({job.group for job in enabled_jobs})
        for group in groups:
            group_jobs = [j.id for j in enabled_jobs if j.group == group]
            logger.info("[%s] Scheduled: %s", group.upper(), group_jobs)

        if disabled_jobs:
            logger.info(
                "Paused %d disabled job(s): %s",
                len(disabled_jobs),
                [job.id for job in disabled_jobs],
            )

        for scheduled_job in scheduler.get_jobs():
            logger.info(
                "Job '%s' next run at %s",
                scheduled_job.id,
                scheduled_job.next_run_time,
            )

    def get_live_job(self, job_id: str):
        """
        Get the live APScheduler Job for a registered job id, reflecting its
        current paused/active state and next run time.
        :param job_id: The job id to look up.
        :return: The live apscheduler.job.Job instance.
        """
        return self.scheduler.get_job(job_id)

    def pause(self, job_id: str) -> None:
        """
        Pause a live, already-registered job.
        :param job_id: The job id to pause.
        """
        self.scheduler.pause_job(job_id)

    def resume(self, job_id: str) -> None:
        """
        Resume a live, already-registered job.
        :param job_id: The job id to resume.
        """
        self.scheduler.resume_job(job_id)

    def reschedule(self, job_id: str, trigger: BaseTrigger) -> None:
        """
        Replace a live job's trigger without touching its paused/active state.
        APScheduler's own reschedule_job() always computes a concrete next
        run time, which would silently resume a paused job - so a paused
        job is re-paused immediately after rescheduling it.
        :param job_id: The job id to reschedule.
        :param trigger: The new trigger to apply.
        """
        was_paused = self.scheduler.get_job(job_id).next_run_time is None
        self.scheduler.reschedule_job(job_id, trigger=trigger)
        if was_paused:
            self.scheduler.pause_job(job_id)
