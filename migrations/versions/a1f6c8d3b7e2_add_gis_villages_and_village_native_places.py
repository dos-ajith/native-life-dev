"""add gis villages and point native places at villages

Revision ID: a1f6c8d3b7e2
Revises: edc738870d55
Create Date: 2026-10-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f6c8d3b7e2'
down_revision: Union[str, Sequence[str], None] = 'edc738870d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gis_villages',
        sa.Column('taluk_id', sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(['taluk_id'], ['gis_taluks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lgd_code'),
    )
    op.create_index('ix_gis_villages_taluk_id', 'gis_villages', ['taluk_id'], unique=False)
    op.create_index(
        'ix_gis_villages_geom', 'gis_villages', ['geom'], unique=False, postgresql_using='gist'
    )

    op.execute('DELETE FROM user_native_places')
    op.drop_constraint('uq_user_native_places_user_id_taluk_id', 'user_native_places', type_='unique')
    op.drop_column('user_native_places', 'taluk_id')
    op.add_column('user_native_places', sa.Column('village_id', sa.Uuid(), nullable=False))
    op.create_foreign_key(
        'user_native_places_village_id_fkey',
        'user_native_places',
        'gis_villages',
        ['village_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_unique_constraint(
        'uq_user_native_places_user_id_village_id', 'user_native_places', ['user_id', 'village_id']
    )


def downgrade() -> None:
    op.execute('DELETE FROM user_native_places')
    op.drop_constraint('uq_user_native_places_user_id_village_id', 'user_native_places', type_='unique')
    op.drop_constraint('user_native_places_village_id_fkey', 'user_native_places', type_='foreignkey')
    op.drop_column('user_native_places', 'village_id')
    op.add_column('user_native_places', sa.Column('taluk_id', sa.Uuid(), nullable=False))
    op.create_foreign_key(
        'user_native_places_taluk_id_fkey',
        'user_native_places',
        'gis_taluks',
        ['taluk_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_unique_constraint(
        'uq_user_native_places_user_id_taluk_id', 'user_native_places', ['user_id', 'taluk_id']
    )
    op.drop_index('ix_gis_villages_geom', table_name='gis_villages', postgresql_using='gist')
    op.drop_index('ix_gis_villages_taluk_id', table_name='gis_villages')
    op.drop_table('gis_villages')
