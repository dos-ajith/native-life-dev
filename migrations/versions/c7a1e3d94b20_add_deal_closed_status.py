"""add closed deal status

Revision ID: c7a1e3d94b20
Revises: b4d8e2f61a95
Create Date: 2026-11-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c7a1e3d94b20'
down_revision: Union[str, Sequence[str], None] = 'b4d8e2f61a95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE deal_status ADD VALUE IF NOT EXISTS 'closed' AFTER 'published'")


def downgrade() -> None:
    pass
