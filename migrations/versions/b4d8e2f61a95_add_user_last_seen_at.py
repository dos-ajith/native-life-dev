"""add user last seen at

Revision ID: b4d8e2f61a95
Revises: 9c69c70403ba
Create Date: 2026-11-04 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d8e2f61a95'
down_revision: Union[str, Sequence[str], None] = '9c69c70403ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'last_seen_at')
