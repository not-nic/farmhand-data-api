"""add_info_layer_and_farmlands_tables

Revision ID: e1b752c145e9
Revises: 8f0b40e2ee12
Create Date: 2026-08-07 21:28:04.181001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b752c145e9'
down_revision: Union[str, None] = '8f0b40e2ee12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('map_info_layers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('map_id', sa.Integer(), nullable=False),
    sa.Column('layer_key', sa.String(length=100), nullable=False),
    sa.Column('i3d_file_id', sa.String(length=50), nullable=True),
    sa.Column('grle_filename', sa.String(length=255), nullable=True),
    sa.Column('asset_uri', sa.String(length=500), nullable=True),
    sa.Column('is_ingested', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['map_id'], ['maps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_map_info_layers_is_ingested'), 'map_info_layers', ['is_ingested'], unique=False)
    op.create_index(op.f('ix_map_info_layers_map_id'), 'map_info_layers', ['map_id'], unique=False)

    op.create_table('map_farmlands',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('map_id', sa.Integer(), nullable=False),
    sa.Column('info_layer_id', sa.UUID(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('price_per_ha', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('price_scale', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('default', sa.Boolean(), nullable=False),
    sa.Column('coordinates', sa.JSON(), nullable=True),
    sa.Column('size_ha', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['info_layer_id'], ['map_info_layers.id'], ),
    sa.ForeignKeyConstraint(['map_id'], ['maps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_map_farmlands_map_id'), 'map_farmlands', ['map_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_map_farmlands_map_id'), table_name='map_farmlands')
    op.drop_table('map_farmlands')

    op.drop_index(op.f('ix_map_info_layers_map_id'), table_name='map_info_layers')
    op.drop_index(op.f('ix_map_info_layers_is_ingested'), table_name='map_info_layers')
    op.drop_table('map_info_layers')
