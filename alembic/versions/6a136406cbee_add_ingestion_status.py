"""add_ingestion_status

Revision ID: 6a136406cbee
Revises: 62554e655e86
Create Date: 2026-06-21 20:17:36.121863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a136406cbee'
down_revision: Union[str, None] = '62554e655e86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'maps',
        sa.Column(
            'ingestion_status',
            sa.Enum('PENDING', 'DOWNLOADING' 'DOWNLOADED', 'EXTRACTED', 'PARSED', 'COMPLETE', 'FAILED',
                    name='ingestionstatus', native_enum=False, length=20),
            nullable=False,
            server_default='PENDING',  # backfills existing rows
        ),
    )
    op.add_column('maps', sa.Column('ingestion_error', sa.Text(), nullable=True))
    op.add_column(
        'maps',
        sa.Column(
            'ingestion_updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now()
        ),
    )

    op.create_index(op.f('ix_maps_category'), 'maps', ['category'], unique=False)
    op.create_index(op.f('ix_maps_id'), 'maps', ['id'], unique=False)
    op.create_index(op.f('ix_maps_ingestion_status'), 'maps', ['ingestion_status'], unique=False)

    # Remove the server default once items have been populated.
    op.alter_column('maps', 'ingestion_status', server_default=None)
    op.alter_column('maps', 'ingestion_updated_at', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_maps_ingestion_status'), table_name='maps')
    op.drop_index(op.f('ix_maps_id'), table_name='maps')
    op.drop_index(op.f('ix_maps_category'), table_name='maps')
    op.drop_column('maps', 'ingestion_updated_at')
    op.drop_column('maps', 'ingestion_error')
    op.drop_column('maps', 'ingestion_status')
