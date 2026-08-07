"""add_tasks

Revision ID: 1ba49cd43dd6
Revises: 8f0b40e2ee12
Create Date: 2026-08-05 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1ba49cd43dd6"
down_revision: Union[str, None] = "8f0b40e2ee12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("trigger_args", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_job_id"), "tasks", ["job_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tasks_job_id"), table_name="tasks")
    op.drop_table("tasks")
