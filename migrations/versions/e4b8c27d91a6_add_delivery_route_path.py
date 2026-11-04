"""add delivery route path

Revision ID: e4b8c27d91a6
Revises: d3a7e19b5c42
Create Date: 2026-11-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


revision: str = 'e4b8c27d91a6'
down_revision: Union[str, Sequence[str], None] = 'd3a7e19b5c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'delivery_routes',
        sa.Column(
            'path',
            geoalchemy2.types.Geometry(
                geometry_type='LINESTRING', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('delivery_routes', 'path')
