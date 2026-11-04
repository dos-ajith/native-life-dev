"""add delivery vehicles and routes

Revision ID: 567687282bf2
Revises: 60a55a713bf5
Create Date: 2026-10-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '567687282bf2'
down_revision: Union[str, Sequence[str], None] = '60a55a713bf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

vehicle_type = postgresql.ENUM('bicycle', 'bike', 'auto', 'van', 'truck', name='vehicle_type', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    vehicle_type.create(op.get_bind(), checkfirst=True)
    op.create_table('delivery_vehicles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_type', vehicle_type, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_delivery_vehicles_user_id', 'delivery_vehicles', ['user_id'], unique=False)
    op.create_table('delivery_routes',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('village_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('start_point', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('end_point', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('coverage_radius_m', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['village_id'], ['gis_villages.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['delivery_vehicles.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_delivery_routes_user_id', 'delivery_routes', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_delivery_routes_user_id', table_name='delivery_routes')
    op.drop_table('delivery_routes')
    op.drop_index('ix_delivery_vehicles_user_id', table_name='delivery_vehicles')
    op.drop_table('delivery_vehicles')
    vehicle_type.drop(op.get_bind(), checkfirst=True)
