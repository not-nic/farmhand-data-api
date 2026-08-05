"""
Python module containing a Repository for scheduled task overrides.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.api.core.db.models.tasks import Task
from src.api.core.repositories import Repository


class TaskRepository(Repository[Task]):
    """
    Repository for Task database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, Task)

    def get_by_job_id(self, job_id: str) -> Task | None:
        """
        Get the override for a given job ID.
        :param job_id: The JobModel.id to look up.
        :return: Task if an override exists, else None.
        """
        return self.db.query(self.model).filter(self.model.job_id == job_id).first()

    def all_by_job_id(self) -> dict[str, Task]:
        """
        Get every stored override, keyed by job_id, for applying at scheduler startup.
        :return: A dict of job_id -> Task.
        """
        return {task.job_id: task for task in self.all()}

    def upsert(self, job_id: str, **kwargs: Any) -> Task:
        """
        Create or update the override for a given job ID. Only the fields
        passed in kwargs are changed - omit a field to leave it as-is on
        an existing override.
        :param job_id: The JobModel.id this override applies to.
        :param kwargs: Fields to set, e.g. enabled=False, trigger_args={"minutes": 5}.
        :return: The created or updated Task.
        """
        existing = self.get_by_job_id(job_id)
        if existing:
            return self.update(existing, **kwargs)
        return self.create(job_id=job_id, **kwargs)

    def delete_by_job_id(self, job_id: str) -> None:
        """
        Remove the override for a given job ID, if one exists, resetting
        it back to its code-defined default.
        :param job_id: The JobModel.id to reset.
        """
        existing = self.get_by_job_id(job_id)
        if existing:
            self.delete(existing)
