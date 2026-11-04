"""add lost found response notification types

Revision ID: d3b9f1a7c5e2
Revises: c7a2e9f4b1d5
Create Date: 2026-11-02 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d3b9f1a7c5e2"
down_revision: Union[str, Sequence[str], None] = "c7a2e9f4b1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'lost_found_found'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'lost_found_claimed'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
