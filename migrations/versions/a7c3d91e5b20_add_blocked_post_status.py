"""add blocked post status

Revision ID: a7c3d91e5b20
Revises: 2f9738e8bb52
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c3d91e5b20'
down_revision: Union[str, Sequence[str], None] = '2f9738e8bb52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE post_status ADD VALUE IF NOT EXISTS 'blocked'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
