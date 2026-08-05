"""
Service for inspecting and controlling scheduled background tasks through
the /tasks API - enabling/disabling jobs and tuning their triggers at
runtime, with changes persisted in the `tasks` table so they survive a
restart.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.api.core.exceptions import InvalidTaskTriggerError
from src.api.core.repositories import TaskRepository
from src.api.core.schema.tasks import TaskStatus, TaskUpdateRequest
from src.api.tasks import base_scheduler
from src.api.tasks.scheduler import JobModel, Scheduler


def _trigger_type(job: JobModel) -> str:
    """
    Human-readable trigger type for a job, derived from its trigger class.
    :param job: The JobModel to inspect.
    :return: e.g. 'interval' for IntervalTrigger, 'cron' for CronTrigger.
    """
    return job.trigger_cls.__name__.removesuffix("Trigger").lower()


class TaskService:
    """
    Service for reading and mutating scheduled background tasks.
    """

    def __init__(self, db: Session, scheduler: Scheduler | None = None):
        self.db = db
        self.repo = TaskRepository(db)
        self.scheduler = scheduler or base_scheduler

    def _effective_trigger_args(self, job: JobModel) -> dict[str, Any]:
        """
        Merge a job's code-defined trigger kwargs with its stored override,
        if any - the args actually in effect right now.
        :param job: The JobModel to resolve args for.
        :return: The effective trigger kwargs.
        """
        override = self.repo.get_by_job_id(job.id)
        return {
            **job.trigger_kwargs,
            **(override.trigger_args if override and override.trigger_args else {}),
        }

    def _to_status(self, job: JobModel) -> TaskStatus:
        """
        Build a TaskStatus from a JobModel's code definition and its live
        APScheduler state.
        :param job: The JobModel to build a status for.
        :return: The resolved TaskStatus.
        """
        live_job = self.scheduler.get_live_job(job.id)
        paused = live_job.next_run_time is None

        return TaskStatus(
            id=job.id,
            name=job.name,
            group=job.group,
            executor=job.executor,
            enabled=not paused,
            paused=paused,
            next_run_time=live_job.next_run_time,
            trigger_type=_trigger_type(job),
            trigger_args=self._effective_trigger_args(job),
        )

    def list_tasks(self) -> list[TaskStatus]:
        """
        List every registered task with its resolved, live state.
        :return: A TaskStatus for every job.
        """
        return [self._to_status(job) for job in self.scheduler.jobs]

    def get_task(self, job_id: str) -> TaskStatus:
        """
        Get a single task's resolved, live state.
        :param job_id: The job id to look up.
        :return: The resolved TaskStatus.
        :raises UnknownTaskError: if job_id is not a registered job.
        """
        job = self.scheduler.get_job(job_id)
        return self._to_status(job)

    def update_task(self, job_id: str, request: TaskUpdateRequest) -> TaskStatus:
        """
        Apply a partial update to a task - enable/disable it, change its
        trigger args, or both. Persists the change to the `tasks` table and
        applies it to the live scheduler immediately.
        :param job_id: The job id to update.
        :param request: The fields to change.
        :return: The resolved TaskStatus after the update.
        :raises UnknownTaskError: if job_id is not a registered job.
        :raises InvalidTaskTriggerError: if trigger_args are invalid for the job's trigger type.
        """
        job = self.scheduler.get_job(job_id)
        update_fields: dict[str, Any] = {}

        if request.trigger_args is not None:
            merged_args = {**self._effective_trigger_args(job), **request.trigger_args}
            try:
                new_trigger = self.scheduler.build_trigger(job, merged_args)
            except (TypeError, ValueError) as exc:
                raise InvalidTaskTriggerError(
                    f"Invalid trigger_args for task '{job_id}': {exc}"
                ) from exc

            update_fields["trigger_args"] = merged_args

        if request.enabled is not None:
            update_fields["enabled"] = request.enabled

        if update_fields:
            self.repo.upsert(job_id, **update_fields)

        if request.trigger_args is not None:
            self.scheduler.reschedule(job_id, new_trigger)
        if request.enabled is not None:
            self.scheduler.resume(job_id) if request.enabled else self.scheduler.pause(job_id)

        return self.get_task(job_id)

    def reset_task(self, job_id: str) -> TaskStatus:
        """
        Remove any stored override for a task and reapply its code-defined
        default live, without an app restart.
        :param job_id: The job id to reset.
        :return: The resolved TaskStatus after resetting.
        :raises UnknownTaskError: if job_id is not a registered job.
        """
        job = self.scheduler.get_job(job_id)
        self.repo.delete_by_job_id(job_id)

        default_trigger = self.scheduler.build_trigger(job)
        self.scheduler.reschedule(job_id, default_trigger)
        self.scheduler.resume(job_id) if job.enabled else self.scheduler.pause(job_id)

        return self.get_task(job_id)
