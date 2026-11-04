"""add business submitted notification type

Revision ID: f2a6c8d41b37
Revises: e8b3d5f20a14
Create Date: 2026-11-04 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f2a6c8d41b37'
down_revision: Union[str, Sequence[str], None] = 'e8b3d5f20a14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'business_submitted'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
