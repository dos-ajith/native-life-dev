"""add deal delivery options

Revision ID: d3f5a8c1e472
Revises: c7a1e3d94b20
Create Date: 2026-11-09 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'd3f5a8c1e472'
down_revision: Union[str, Sequence[str], None] = 'c7a1e3d94b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'deals',
        sa.Column(
            'delivery_options',
            postgresql.ARRAY(sa.String(length=20)),
            server_default=sa.text("ARRAY['instant','route','self_pickup']::varchar[]"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('deals', 'delivery_options')
