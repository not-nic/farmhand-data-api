"""
API Routes for inspecting and controlling scheduled background tasks.

This allows enabling/disabling a job and tuning its trigger (interval,
cron fields, start time) at runtime, without an app restart or code
change - useful for turning pipeline jobs off during local development.

Routes:
    - GET /tasks: List every registered task and its resolved, live state.
    - GET /tasks/{job_id}: Get a single task's resolved, live state.
    - PATCH /tasks/{job_id}: Partially update a task's enabled state and/or trigger args.
    - DELETE /tasks/{job_id}/reset: Remove a task's override, reverting it to its code default.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.core.dependencies import SessionDep
from src.api.core.exceptions import InvalidTaskTriggerError, UnknownTaskError
from src.api.core.schema.tasks import TaskStatus, TaskUpdateRequest
from src.api.services.tasks import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/", status_code=status.HTTP_200_OK)
async def list_tasks(db: SessionDep) -> list[TaskStatus]:
    """
    List every registered scheduled task and its resolved, live state.
    :param db: Database session dependency.
    :return: A TaskStatus for every job.
    """
    return TaskService(db).list_tasks()


@router.get("/{job_id}", status_code=status.HTTP_200_OK)
async def get_task(job_id: str, db: SessionDep) -> TaskStatus:
    """
    Get a single scheduled task's resolved, live state.
    :param job_id: The job id to look up, e.g. 'download_pending_maps'.
    :param db: Database session dependency.
    :return: The resolved TaskStatus.
    """
    try:
        return TaskService(db).get_task(job_id)
    except UnknownTaskError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{job_id}", status_code=status.HTTP_200_OK)
async def update_task(job_id: str, request: TaskUpdateRequest, db: SessionDep) -> TaskStatus:
    """
    Partially update a scheduled task - enable/disable it, change its
    trigger args, or both. Persisted so the change survives a restart.
    :param job_id: The job id to update.
    :param request: The fields to change.
    :param db: Database session dependency.
    :return: The resolved TaskStatus after the update.
    """
    try:
        return TaskService(db).update_task(job_id, request)
    except UnknownTaskError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidTaskTriggerError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.delete("/{job_id}/reset", status_code=status.HTTP_200_OK)
async def reset_task(job_id: str, db: SessionDep) -> TaskStatus:
    """
    Remove a task's stored override, reverting it to its code-defined
    default live, without an app restart.
    :param job_id: The job id to reset.
    :param db: Database session dependency.
    :return: The resolved TaskStatus after resetting.
    """
    try:
        return TaskService(db).reset_task(job_id)
    except UnknownTaskError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
