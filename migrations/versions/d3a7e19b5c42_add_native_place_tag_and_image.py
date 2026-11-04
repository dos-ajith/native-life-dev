"""add native place tag name and image

Revision ID: d3a7e19b5c42
Revises: c8d2f4a61b93
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3a7e19b5c42'
down_revision: Union[str, Sequence[str], None] = 'c8d2f4a61b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gis_villages', sa.Column('tag_name', sa.String(length=150), nullable=True))
    op.add_column('gis_villages', sa.Column('image_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column('gis_villages', 'image_url')
    op.drop_column('gis_villages', 'tag_name')
