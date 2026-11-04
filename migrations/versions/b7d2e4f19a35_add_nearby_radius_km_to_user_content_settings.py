"""add nearby radius km to user content settings

Revision ID: b7d2e4f19a35
Revises: a1f6c8d3b7e2
Create Date: 2026-10-13 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d2e4f19a35'
down_revision: Union[str, Sequence[str], None] = 'a1f6c8d3b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_content_settings',
        sa.Column('nearby_radius_km', sa.Integer(), nullable=False, server_default='30'),
    )
    op.alter_column('user_content_settings', 'nearby_radius_km', server_default=None)


def downgrade() -> None:
    op.drop_column('user_content_settings', 'nearby_radius_km')
