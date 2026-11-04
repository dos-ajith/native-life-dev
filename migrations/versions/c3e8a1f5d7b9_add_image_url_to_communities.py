"""add image_url to communities

Revision ID: c3e8a1f5d7b9
Revises: 9325539c08a3
Create Date: 2026-10-14 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e8a1f5d7b9'
down_revision: Union[str, Sequence[str], None] = '9325539c08a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('communities', sa.Column('image_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'image_url')
