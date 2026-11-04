"""add category suggested notification type

Revision ID: f6b0d4e2a8c3
Revises: e5a9c3d1f7b2
Create Date: 2026-10-07 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6b0d4e2a8c3"
down_revision: Union[str, Sequence[str], None] = "e5a9c3d1f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'category_suggested'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
