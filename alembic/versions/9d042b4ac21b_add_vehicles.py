"""add_vehicles

Add the base game / DLC vehicle catalogue (vehicles, their motor and fill unit
configurations, and map starting vehicles), and replace the polymorphic
entity_type/entity_id on assets with nullable map_id and vehicle_id foreign keys,
so maps and vehicles share one assets table.

Revision ID: 9d042b4ac21b
Revises: f6fd0ebea429
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d042b4ac21b'
down_revision: Union[str, None] = 'f6fd0ebea429'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('vehicles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('config_path', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('brand', sa.String(length=255), nullable=True),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('category_label', sa.String(length=100), nullable=True),
    sa.Column('vehicle_type', sa.String(length=100), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('dlc', sa.String(length=100), nullable=True),
    sa.Column('image', sa.String(length=255), nullable=True),
    sa.Column('weight', sa.Integer(), nullable=True),
    sa.Column('working_speed', sa.Integer(), nullable=True),
    sa.Column('working_width', sa.Float(), nullable=True),
    sa.Column('needed_power', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vehicles_category'), 'vehicles', ['category'], unique=False)
    op.create_index(op.f('ix_vehicles_config_path'), 'vehicles', ['config_path'], unique=True)
    op.create_index(op.f('ix_vehicles_vehicle_type'), 'vehicles', ['vehicle_type'], unique=False)

    op.create_table('vehicle_motor_configurations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('vehicle_id', sa.UUID(), nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('vehicle_name', sa.String(length=255), nullable=True),
    sa.Column('hp', sa.Integer(), nullable=True),
    sa.Column('max_speed', sa.Integer(), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vehicle_id', 'index', name='uq_vehicle_motor_index')
    )
    op.create_index(op.f('ix_vehicle_motor_configurations_vehicle_id'), 'vehicle_motor_configurations', ['vehicle_id'], unique=False)

    op.create_table('vehicle_fill_unit_configurations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('vehicle_id', sa.UUID(), nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.Column('fill_units', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vehicle_id', 'index', name='uq_vehicle_fill_unit_index')
    )
    op.create_index(op.f('ix_vehicle_fill_unit_configurations_vehicle_id'), 'vehicle_fill_unit_configurations', ['vehicle_id'], unique=False)

    op.create_table('map_vehicles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('map_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.UUID(), nullable=False),
    sa.Column('motor_configuration_id', sa.UUID(), nullable=True),
    sa.Column('fill_unit_configuration_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['fill_unit_configuration_id'], ['vehicle_fill_unit_configurations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['map_id'], ['maps.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['motor_configuration_id'], ['vehicle_motor_configurations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_map_vehicles_map_id'), 'map_vehicles', ['map_id'], unique=False)

    # Assets: one nullable foreign key per owner instead of entity_type/entity_id.
    op.add_column('assets', sa.Column('map_id', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('vehicle_id', sa.UUID(), nullable=True))

    # Every existing asset is a map asset.
    op.execute("UPDATE assets SET map_id = entity_id")
    # Drop assets whose map no longer exists, so the foreign key can be created.
    op.execute("DELETE FROM assets WHERE map_id NOT IN (SELECT id FROM maps)")
    # Keep only the newest (uuid7) asset per map and type, so the unique constraint holds.
    op.execute(
        "DELETE FROM assets a USING assets b "
        "WHERE a.map_id = b.map_id AND a.asset_type = b.asset_type AND a.id < b.id"
    )

    op.drop_index('ix_assets_entity', table_name='assets')
    op.drop_column('assets', 'entity_id')
    op.drop_column('assets', 'entity_type')

    op.create_foreign_key(
        'fk_assets_map_id_maps', 'assets', 'maps', ['map_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_assets_vehicle_id_vehicles', 'assets', 'vehicles', ['vehicle_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_assets_map_id'), 'assets', ['map_id'], unique=False)
    op.create_index(op.f('ix_assets_vehicle_id'), 'assets', ['vehicle_id'], unique=False)
    op.create_unique_constraint('uq_assets_map_asset_type', 'assets', ['map_id', 'asset_type'])
    op.create_unique_constraint('uq_assets_vehicle_asset_type', 'assets', ['vehicle_id', 'asset_type'])
    op.create_check_constraint(
        'ck_assets_single_owner', 'assets', '(map_id IS NULL) <> (vehicle_id IS NULL)'
    )


def downgrade() -> None:
    """Downgrade schema. Vehicle assets cannot be represented and are deleted."""
    op.drop_constraint('ck_assets_single_owner', 'assets', type_='check')
    op.drop_constraint('uq_assets_vehicle_asset_type', 'assets', type_='unique')
    op.drop_constraint('uq_assets_map_asset_type', 'assets', type_='unique')
    op.drop_index(op.f('ix_assets_vehicle_id'), table_name='assets')
    op.drop_index(op.f('ix_assets_map_id'), table_name='assets')
    op.drop_constraint('fk_assets_vehicle_id_vehicles', 'assets', type_='foreignkey')
    op.drop_constraint('fk_assets_map_id_maps', 'assets', type_='foreignkey')

    op.execute("DELETE FROM assets WHERE map_id IS NULL")

    op.add_column('assets', sa.Column(
        'entity_type',
        sa.Enum('MAP', name='entitytype', native_enum=False, length=20),
        nullable=True,
    ))
    op.add_column('assets', sa.Column('entity_id', sa.Integer(), nullable=True))
    op.execute("UPDATE assets SET entity_type = 'MAP', entity_id = map_id")
    op.alter_column('assets', 'entity_type', nullable=False)
    op.alter_column('assets', 'entity_id', nullable=False)
    op.create_index('ix_assets_entity', 'assets', ['entity_type', 'entity_id', 'is_ingested'], unique=False)

    op.drop_column('assets', 'vehicle_id')
    op.drop_column('assets', 'map_id')

    op.drop_index(op.f('ix_map_vehicles_map_id'), table_name='map_vehicles')
    op.drop_table('map_vehicles')
    op.drop_index(op.f('ix_vehicle_fill_unit_configurations_vehicle_id'), table_name='vehicle_fill_unit_configurations')
    op.drop_table('vehicle_fill_unit_configurations')
    op.drop_index(op.f('ix_vehicle_motor_configurations_vehicle_id'), table_name='vehicle_motor_configurations')
    op.drop_table('vehicle_motor_configurations')
    op.drop_index(op.f('ix_vehicles_vehicle_type'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_config_path'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_category'), table_name='vehicles')
    op.drop_table('vehicles')
