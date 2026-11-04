"""add last_read_at to community members

Revision ID: f2b8d5c3a7e1
Revises: e1a7c4b9d2f6
Create Date: 2026-10-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b8d5c3a7e1'
down_revision: Union[str, Sequence[str], None] = 'e1a7c4b9d2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('community_members', sa.Column('last_read_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('community_members', 'last_read_at')
