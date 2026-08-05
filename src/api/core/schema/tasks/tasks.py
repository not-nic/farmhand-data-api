"""
Module containing Task pydantic models.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskStatus(BaseModel):
    """
    Pydantic model describing the resolved, live state of a scheduled task -
    the code-defined default merged with any stored override.
    """

    id: str
    name: str | None = None
    group: str
    executor: str
    enabled: bool
    paused: bool
    next_run_time: datetime | None = None
    trigger_type: str
    trigger_args: dict[str, Any]


class TaskUpdateRequest(BaseModel):
    """
    Pydantic model for a partial task update. Only the fields provided are
    changed - omit a field to leave it as-is.
    """

    enabled: bool | None = None
    trigger_args: dict[str, Any] | None = None
