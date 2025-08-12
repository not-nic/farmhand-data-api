"""
Module containing a singleton utility for scheduling jobs with APScheduler.
"""

import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.base import BaseTrigger


@dataclass
class JobModel:
    """
    Dataclass for the job model to instantiate new background tasks.
    """
    func: Callable[..., Any]
    trigger: BaseTrigger
    id: str
    name: Optional[str] = None
    args: Optional[list] = None
    kwargs: Optional[dict] = None
    replace_existing: bool = True


class Scheduler:
    """
    Singleton Scheduler class for scheduling all jobs defined in the modules __init__.py
    on the FastAPI application start up.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """
        Create this class as a singleton.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.jobs = []
        return cls._instance

    def add_job(self, job: JobModel):
        """
        Method to add a new job to the scheduler.
        :param job: The job model to schedule.
        """
        self.jobs.append(job)

    def schedule_jobs(self, scheduler: BaseScheduler):
        """
        Schedule each job stored in the array into the APScheduler instance.
        :param scheduler: The APScheduler instance.
        """
        for job in self.jobs:
            scheduler.add_job(
                func=job.func,
                trigger=job.trigger,
                id=job.id,
                name=job.name,
                args=job.args,
                kwargs=job.kwargs,
                replace_existing=job.replace_existing
            )


