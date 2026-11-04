"""add lost found closed notification type

Revision ID: e4c0a2b8d6f3
Revises: d3b9f1a7c5e2
Create Date: 2026-11-02 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e4c0a2b8d6f3"
down_revision: Union[str, Sequence[str], None] = "d3b9f1a7c5e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'lost_found_closed'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
