"""
SQLAlchemy model for a runtime override of a scheduled background task.
"""

from datetime import datetime
from uuid import uuid7

from sqlalchemy import JSON, UUID, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.api.core.db.models._model_base import SqlAlchemyBase


class Task(SqlAlchemyBase):
    """
    Persisted override for a code-defined scheduler job (see
    `src.api.tasks.scheduler.JobModel`). A row only needs to exist once a
    job's default has been changed via the `/tasks` API - missing fields
    (`None`) mean "use the code-defined default".

    Attributes:
        id: UUID primary key.
        job_id: The JobModel.id this override applies to, e.g. 'download_pending_maps'.
        enabled: Overrides the job's enabled state, None to fall back to the code default.
        trigger_args: Overrides merged over the job's default trigger kwargs, e.g.
            {"minutes": 5} for an interval job or {"hour": 9} for a cron job.
        updated_at: When this override was last changed.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid7)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    trigger_args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
