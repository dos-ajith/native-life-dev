"""add role_upgrade_requested notification type

Revision ID: 410345c8d288
Revises: 8e96b0fd679f
Create Date: 2026-10-01 14:58:29.323814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '410345c8d288'
down_revision: Union[str, Sequence[str], None] = '8e96b0fd679f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'role_upgrade_requested'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
