"""create gis states districts and taluks tables

Revision ID: 13e6fd5324e7
Revises: 5d380292b207
Create Date: 2026-09-18 15:18:48.223637

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13e6fd5324e7'
down_revision: Union[str, Sequence[str], None] = '5d380292b207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

    op.create_table(
        'gis_states',
        sa.Column('lgd_code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column(
            'geom',
            geoalchemy2.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False),
            nullable=False,
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lgd_code'),
    )
    op.create_index(
        'ix_gis_states_geom', 'gis_states', ['geom'], unique=False, postgresql_using='gist'
    )

    op.create_table(
        'gis_districts',
        sa.Column('state_id', sa.Uuid(), nullable=False),
        sa.Column('lgd_code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column(
            'geom',
            geoalchemy2.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False),
            nullable=False,
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['state_id'], ['gis_states.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lgd_code'),
    )
    op.create_index(
        'ix_gis_districts_geom', 'gis_districts', ['geom'], unique=False, postgresql_using='gist'
    )
    op.create_index('ix_gis_districts_state_id', 'gis_districts', ['state_id'], unique=False)

    op.create_table(
        'gis_taluks',
        sa.Column('district_id', sa.Uuid(), nullable=False),
        sa.Column('lgd_code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column(
            'geom',
            geoalchemy2.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False),
            nullable=False,
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['district_id'], ['gis_districts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lgd_code'),
    )
    op.create_index(
        'ix_gis_taluks_geom', 'gis_taluks', ['geom'], unique=False, postgresql_using='gist'
    )
    op.create_index('ix_gis_taluks_district_id', 'gis_taluks', ['district_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_gis_taluks_district_id', table_name='gis_taluks')
    op.drop_index('ix_gis_taluks_geom', table_name='gis_taluks')
    op.drop_table('gis_taluks')

    op.drop_index('ix_gis_districts_state_id', table_name='gis_districts')
    op.drop_index('ix_gis_districts_geom', table_name='gis_districts')
    op.drop_table('gis_districts')

    op.drop_index('ix_gis_states_geom', table_name='gis_states')
    op.drop_table('gis_states')
