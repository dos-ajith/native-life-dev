"""add deal cancelled notification types

Revision ID: a7c3e9d15b42
Revises: f3b8d1a2c4e6
Create Date: 2026-11-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c3e9d15b42'
down_revision: Union[str, Sequence[str], None] = 'f3b8d1a2c4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'deal_cancelled'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'deal_order_cancelled'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'deal_order_refund_due'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
