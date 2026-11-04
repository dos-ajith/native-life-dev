"""add business location

Revision ID: a7d3c9e5b1f4
Revises: f6b0d4e2a8c3
Create Date: 2026-10-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa


revision: str = 'a7d3c9e5b1f4'
down_revision: Union[str, Sequence[str], None] = 'f6b0d4e2a8c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'businesses',
        sa.Column(
            'location',
            geoalchemy2.Geometry(
                geometry_type='POINT',
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text='ST_GeomFromEWKT',
                name='geometry',
            ),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_businesses_location_geography',
        'businesses',
        [sa.text('(location::geography)')],
        unique=False,
        postgresql_using='gist',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_businesses_location_geography', table_name='businesses', postgresql_using='gist')
    op.drop_column('businesses', 'location')
