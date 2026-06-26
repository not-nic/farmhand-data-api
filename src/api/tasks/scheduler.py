"""
Module containing a singleton utility for scheduling jobs with APScheduler.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.base import BaseTrigger

from src.api.core.logger import logger


@dataclass
class JobModel:
    """
    Dataclass for a scheduled background job.

    Attributes:
        func: The function to call when the job fires.
        trigger: APScheduler trigger defining when the job runs.
        id: Unique job identifier.
        name: Human-readable job name to be shown in logs.
        group: A group for the job.
        enabled: Set too False to skip registration without removing the job definition.
        args: Positional arguments passed to func.
        kwargs: Keyword arguments passed to func.
        replace_existing: Replace an existing job with the same id on scheduler start.
    """

    func: Callable[..., Any]
    trigger: BaseTrigger
    id: str
    name: str | None = None
    group: str = "general"
    enabled: bool = True
    args: list | None = None
    kwargs: dict | None = None
    replace_existing: bool = True


class Scheduler:
    """
    Singleton Scheduler class for scheduling all jobs defined in the
    tasks __init__.py on FastAPI application startup.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.jobs = []
        return cls._instance

    def add_job(self, job: JobModel) -> None:
        """
        Add a job to the scheduler registry.
        :param job: The JobModel to register.
        """
        self.jobs.append(job)

    def schedule_jobs(self, scheduler: BaseScheduler) -> None:
        """
        Register all enabled jobs with the APScheduler instance and log
        a grouped summary of what was scheduled and what was skipped.
        :param scheduler: The APScheduler instance.
        """
        enabled = [job for job in self.jobs if job.enabled]
        disabled = [job for job in self.jobs if not job.enabled]

        for job in enabled:
            scheduler.add_job(
                func=job.func,
                trigger=job.trigger,
                id=job.id,
                name=job.name,
                args=job.args,
                kwargs=job.kwargs,
                replace_existing=job.replace_existing,
            )

        groups = sorted({job.group for job in enabled})
        for group in groups:
            group_jobs = [j.id for j in enabled if j.group == group]
            logger.info("[%s] Scheduled: %s", group.upper(), group_jobs)

        if disabled:
            logger.info(
                "Skipped %d disabled job(s): %s",
                len(disabled),
                [job.id for job in disabled],
            )

        for scheduled_job in scheduler.get_jobs():
            logger.info(
                "Job '%s' next run at %s",
                scheduled_job.id,
                scheduled_job.next_run_time,
            )
