"""add lost found notification types

Revision ID: c7a2e9f4b1d5
Revises: b4e81f20c6a3
Create Date: 2026-11-02 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7a2e9f4b1d5"
down_revision: Union[str, Sequence[str], None] = "b4e81f20c6a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'lost_found_nearby'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'lost_found_resolved'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
