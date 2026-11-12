"""add deal owner review statuses and notifications

Revision ID: e5b2c9d7a136
Revises: d3f5a8c1e472
Create Date: 2026-11-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5b2c9d7a136'
down_revision: Union[str, Sequence[str], None] = 'd3f5a8c1e472'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFICATION_TYPES = (
    'deal_promoted_for_business',
    'deal_republish_requested',
    'deal_blocked',
    'deal_republish_approved',
    'deal_republish_rejected',
)


def upgrade() -> None:
    op.execute("ALTER TYPE deal_status ADD VALUE IF NOT EXISTS 'blocked' AFTER 'published'")
    op.execute(
        "ALTER TYPE deal_status ADD VALUE IF NOT EXISTS 'pending_owner_approval' AFTER 'blocked'"
    )
    for notification_type in NOTIFICATION_TYPES:
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{notification_type}'")


def downgrade() -> None:
    pass
